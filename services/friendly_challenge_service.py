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


def validate_group_challenge_params(challenger_id, invitee_ids, challenge_type, start_date_str, end_date_str, tz_name="UTC", title=None, message=None):
    """
    Validates parameters for creating a new group challenge (3-10 participants).
    Returns cleaned parameters dictionary.
    """
    if challenger_id is None:
        raise ValueError("Challenger ID is required.")
    if not invitee_ids or not isinstance(invitee_ids, (list, tuple, set)):
        raise ValueError("Group challenges require a list of invited runner IDs.")

    try:
        c_id = int(challenger_id)
        clean_invitees = []
        for inv in invitee_ids:
            clean_invitees.append(int(inv))
    except (ValueError, TypeError):
        raise ValueError("Participant IDs must be valid integers.")

    # Deduplicate while preserving order
    seen = set()
    unique_invitees = []
    for inv in clean_invitees:
        if inv not in seen:
            seen.add(inv)
            unique_invitees.append(inv)

    if c_id in seen:
        raise ValueError("Cannot invite yourself to the challenge.")

    total_participants = len(unique_invitees) + 1
    if total_participants < 3:
        raise ValueError(f"Group challenges require at least 3 total participants (you selected {total_participants}).")
    if total_participants > 10:
        raise ValueError(f"Group challenges support at most 10 total participants (you selected {total_participants}).")

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
        "invitee_ids": unique_invitees,
        "total_participants": total_participants,
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
            INSERT INTO challenge_participants (challenge_id, user_id, invitation_status, final_score, score_unit, result, created_at, updated_at)
            VALUES (?, ?, 'ACCEPTED', 0.0, ?, 'PENDING', ?, ?)
        """, (challenge_id, params["challenger_id"], unit, now_str, now_str))

        conn.execute("""
            INSERT INTO challenge_participants (challenge_id, user_id, invitation_status, final_score, score_unit, result, created_at, updated_at)
            VALUES (?, ?, 'INVITED', 0.0, ?, 'PENDING', ?, ?)
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


def create_group_challenge(challenger_id, invitee_ids, challenge_type, start_date_str, end_date_str,
                           tz_name="UTC", title=None, message=None, expires_hours=48, conn=None):
    """
    Creates a new Free-For-All group challenge invitation (3-10 participants) in a transaction.
    Returns challenge_id.
    """
    params = validate_group_challenge_params(
        challenger_id, invitee_ids, challenge_type,
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

        # For backward compatibility on databases where opponent_id might still have NOT NULL,
        # set opponent_id to the first invitee, while challenge_mode = 'GROUP'.
        first_invitee = params["invitee_ids"][0]

        cursor = conn.execute("""
            INSERT INTO friendly_challenges (
                challenger_id, opponent_id, challenge_type, challenge_mode, max_participants,
                title, message, start_date, end_date, challenge_timezone, status,
                created_at, expires_at, updated_at
            )
            VALUES (?, ?, ?, 'GROUP', ?, ?, ?, ?, ?, ?, 'INVITED', ?, ?, ?)
        """, (
            params["challenger_id"], first_invitee, params["challenge_type"],
            params["total_participants"], params["title"], params["message"],
            params["start_date"], params["end_date"], params["challenge_timezone"],
            now_str, expires_str, now_str
        ))

        # Get last inserted id
        from db import USE_PG as is_pg
        if is_pg and hasattr(cursor, "fetchone"):
            pass
        chal_row = conn.execute(
            "SELECT id FROM friendly_challenges WHERE challenger_id = ? AND challenge_mode = 'GROUP' ORDER BY id DESC LIMIT 1",
            (params["challenger_id"],)
        ).fetchone()
        challenge_id = chal_row["id"] if hasattr(chal_row, "keys") else chal_row[0]

        unit = SCORE_UNITS[params["challenge_type"]]

        # 1. Insert challenger with invitation_status = 'ACCEPTED'
        conn.execute("""
            INSERT INTO challenge_participants (
                challenge_id, user_id, invitation_status, final_score, score_unit, result, created_at, updated_at
            )
            VALUES (?, ?, 'ACCEPTED', 0.0, ?, 'PENDING', ?, ?)
        """, (challenge_id, params["challenger_id"], unit, now_str, now_str))

        # 2. Insert each invited participant with invitation_status = 'INVITED'
        for inv_id in params["invitee_ids"]:
            conn.execute("""
                INSERT INTO challenge_participants (
                    challenge_id, user_id, invitation_status, final_score, score_unit, result, created_at, updated_at
                )
                VALUES (?, ?, 'INVITED', 0.0, ?, 'PENDING', ?, ?)
            """, (challenge_id, inv_id, unit, now_str, now_str))

        # Log activity
        meta = json.dumps({
            "challenge_type": params["challenge_type"],
            "challenge_mode": "GROUP",
            "start_date": params["start_date"],
            "end_date": params["end_date"],
            "invitee_count": len(params["invitee_ids"]),
            "total_participants": params["total_participants"],
        })
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

    tz_name = challenge.get("challenge_timezone") or "UTC"
    current_local_date = now_dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")

    # For scheduled future challenges: start_date arrival closes the invitation window and locks roster
    created_local_date = (challenge.get("created_at") or "")[:10]
    if created_local_date and challenge["start_date"] > created_local_date:
        if current_local_date >= challenge["start_date"]:
            is_expired = True

    # If challenge end_date has already passed in its timezone
    if current_local_date > challenge["end_date"]:
        is_expired = True

    if is_expired:
        should_close = False
        if conn is None:
            conn = get_db()
            should_close = True
        try:
            if challenge.get("challenge_mode") == "GROUP":
                acc_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM challenge_participants WHERE challenge_id = ? AND invitation_status = 'ACCEPTED'",
                    (challenge["id"],)
                ).fetchone()
                acc_cnt = acc_row["cnt"] if acc_row else 0
                if acc_cnt >= 3:
                    # Minimum 3 accepted participants met: roster locks at start, mark remaining unaccepted as expired
                    conn.execute("""
                        UPDATE challenge_participants
                        SET invitation_status = 'EXPIRED', updated_at = ?
                        WHERE challenge_id = ? AND invitation_status = 'INVITED'
                    """, (now_str, challenge["id"]))
                    conn.execute("""
                        UPDATE friendly_challenges
                        SET status = 'ACCEPTED', updated_at = ?
                        WHERE id = ? AND status = 'INVITED'
                    """, (now_str, challenge["id"]))
                    conn.commit()
                    challenge["status"] = "ACCEPTED"
                    return False
                else:
                    # Fewer than 3 accepted at start: do not activate, expire challenge and unaccepted invitees
                    conn.execute("""
                        UPDATE challenge_participants
                        SET invitation_status = 'EXPIRED', updated_at = ?
                        WHERE challenge_id = ? AND invitation_status = 'INVITED'
                    """, (now_str, challenge["id"]))
                    conn.execute("""
                        UPDATE friendly_challenges
                        SET status = 'EXPIRED', updated_at = ?
                        WHERE id = ? AND status = 'INVITED'
                    """, (now_str, challenge["id"]))
                    conn.commit()
                    challenge["status"] = "EXPIRED"
                    return True

            conn.execute("""
                UPDATE challenge_participants
                SET invitation_status = 'EXPIRED', updated_at = ?
                WHERE challenge_id = ? AND invitation_status = 'INVITED'
            """, (now_str, challenge["id"]))
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


def accept_challenge(challenge_id, user_id, now_dt=None, conn=None):
    """Opponent or group invitee accepts challenge invitation."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            raise ValueError("Challenge not found.")
        chal = dict(chal)

        part = conn.execute(
            "SELECT * FROM challenge_participants WHERE challenge_id = ? AND user_id = ?",
            (challenge_id, user_id)
        ).fetchone()

        is_group = (chal.get("challenge_mode") == "GROUP")

        if is_group:
            if int(chal["challenger_id"]) == int(user_id):
                raise PermissionError("Creator is already an accepted participant.")
            if not part:
                raise PermissionError("Only invited participants can accept this challenge.")
            part = dict(part)
            if part.get("invitation_status") == "ACCEPTED":
                return True
            if part.get("invitation_status") != "INVITED":
                raise ValueError(f"Cannot accept challenge with invitation status '{part.get('invitation_status')}'.")
        else:
            if int(chal["opponent_id"]) != int(user_id):
                raise PermissionError("Only the invited opponent can accept this challenge.")
            if chal["status"] != "INVITED":
                raise ValueError(f"Cannot accept challenge with status '{chal['status']}'.")

        now_dt = now_dt or datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Roster locking check: cannot accept if challenge start_date has already arrived for scheduled challenges
        tz_name = chal.get("challenge_timezone") or "UTC"
        current_local_date = now_dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
        created_local_date = (chal.get("created_at") or "")[:10]
        if created_local_date and chal["start_date"] > created_local_date and current_local_date >= chal["start_date"]:
            conn.execute("""
                UPDATE challenge_participants
                SET invitation_status = 'EXPIRED', updated_at = ?
                WHERE challenge_id = ? AND invitation_status = 'INVITED'
            """, (now_str, challenge_id))
            conn.commit()
            raise ValueError("Challenge roster is locked because the challenge has already started.")

        if check_and_update_expiry(chal, now_dt=now_dt, conn=conn):
            raise ValueError("This challenge invitation has expired.")

        # Check maximum participants limit
        if is_group:
            acc_cnt_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM challenge_participants WHERE challenge_id = ? AND invitation_status = 'ACCEPTED'",
                (challenge_id,)
            ).fetchone()
            current_accepted = acc_cnt_row["cnt"] if acc_cnt_row else 0
            max_p = chal.get("max_participants") or 10
            if current_accepted >= max_p:
                raise ValueError(f"Challenge is full (maximum {max_p} participants reached).")

        # Update participant's invitation status
        conn.execute("""
            UPDATE challenge_participants
            SET invitation_status = 'ACCEPTED', updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (now_str, challenge_id, user_id))

        if is_group:
            # Minimum 3 accepted participants required to activate challenge
            acc_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM challenge_participants WHERE challenge_id = ? AND invitation_status = 'ACCEPTED'",
                (challenge_id,)
            ).fetchone()
            acc_cnt = acc_row["cnt"] if acc_row else 0
            if acc_cnt >= 3 and chal["status"] == "INVITED":
                conn.execute("""
                    UPDATE friendly_challenges
                    SET status = 'ACCEPTED', responded_at = COALESCE(responded_at, ?), updated_at = ?
                    WHERE id = ?
                """, (now_str, now_str, challenge_id))
            else:
                conn.execute("UPDATE friendly_challenges SET updated_at = ? WHERE id = ?", (now_str, challenge_id))
        else:
            cur = conn.execute("""
                UPDATE friendly_challenges
                SET status = 'ACCEPTED', responded_at = ?, updated_at = ?
                WHERE id = ? AND status = 'INVITED'
            """, (now_str, now_str, challenge_id))
            if cur.rowcount == 0:
                raise ValueError(f"Cannot accept challenge with status '{chal['status']}'.")

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
    """Opponent or group invitee rejects challenge invitation."""
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True
    try:
        chal = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
        if not chal:
            raise ValueError("Challenge not found.")
        chal = dict(chal)

        part = conn.execute(
            "SELECT * FROM challenge_participants WHERE challenge_id = ? AND user_id = ?",
            (challenge_id, user_id)
        ).fetchone()

        is_group = (chal.get("challenge_mode") == "GROUP")

        if is_group:
            if int(chal["challenger_id"]) == int(user_id):
                raise PermissionError("Creator cannot decline the challenge.")
            if not part:
                raise PermissionError("Only invited participants can reject this challenge.")
            part = dict(part)
            if part.get("invitation_status") != "INVITED":
                raise ValueError(f"Cannot reject challenge with invitation status '{part.get('invitation_status')}'.")
        else:
            if int(chal["opponent_id"]) != int(user_id):
                raise PermissionError("Only the invited opponent can reject this challenge.")
            if chal["status"] != "INVITED":
                raise ValueError(f"Cannot reject challenge with status '{chal['status']}'.")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            UPDATE challenge_participants
            SET invitation_status = 'REJECTED', result = 'DECLINED', updated_at = ?
            WHERE challenge_id = ? AND user_id = ?
        """, (now_str, challenge_id, user_id))

        if is_group:
            # Check remaining potential runners (ACCEPTED or still INVITED)
            rem_row = conn.execute("""
                SELECT COUNT(*) as cnt FROM challenge_participants
                WHERE challenge_id = ? AND invitation_status IN ('INVITED', 'ACCEPTED')
            """, (challenge_id,)).fetchone()
            rem_cnt = rem_row["cnt"] if rem_row else 0
            if rem_cnt < 3 and chal["status"] == "INVITED":
                # Minimum 3 can never be met; transition challenge to REJECTED
                conn.execute("""
                    UPDATE friendly_challenges
                    SET status = 'REJECTED', responded_at = COALESCE(responded_at, ?), updated_at = ?
                    WHERE id = ?
                """, (now_str, now_str, challenge_id))
            else:
                conn.execute("UPDATE friendly_challenges SET updated_at = ? WHERE id = ?", (now_str, challenge_id))
        else:
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


def cancel_challenge(challenge_id, user_id, target_user_id=None, conn=None):
    """Challenger cancels challenge invitation or a specific participant invitation before response."""
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

        is_group = (chal.get("challenge_mode") == "GROUP")

        if target_user_id is not None:
            if int(target_user_id) == int(user_id):
                raise ValueError("Cannot cancel creator's participation.")

            part = conn.execute(
                "SELECT * FROM challenge_participants WHERE challenge_id = ? AND user_id = ?",
                (challenge_id, target_user_id)
            ).fetchone()
            if not part:
                raise ValueError("Participant not found.")
            part = dict(part)
            if part.get("invitation_status") != "INVITED":
                raise ValueError(f"Cannot cancel invitation with status '{part.get('invitation_status')}'.")

            conn.execute("""
                UPDATE challenge_participants
                SET invitation_status = 'CANCELLED', result = 'CANCELLED', updated_at = ?
                WHERE challenge_id = ? AND user_id = ?
            """, (now_str, challenge_id, target_user_id))

            conn.execute("""
                INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, created_at)
                VALUES (?, ?, 'CANCELLED', ?)
            """, (challenge_id, user_id, now_str))

            if not is_group:
                conn.execute("""
                    UPDATE friendly_challenges
                    SET status = 'CANCELLED', updated_at = ?
                    WHERE id = ?
                """, (now_str, challenge_id))
            else:
                # If remaining potential runners falls below 3, cancel the entire challenge
                rem_row = conn.execute("""
                    SELECT COUNT(*) as cnt FROM challenge_participants
                    WHERE challenge_id = ? AND invitation_status IN ('INVITED', 'ACCEPTED')
                """, (challenge_id,)).fetchone()
                rem_cnt = rem_row["cnt"] if rem_row else 0
                if rem_cnt < 3:
                    conn.execute("""
                        UPDATE friendly_challenges
                        SET status = 'CANCELLED', updated_at = ?
                        WHERE id = ?
                    """, (now_str, challenge_id))
                    conn.execute("""
                        UPDATE challenge_participants
                        SET invitation_status = 'CANCELLED', result = 'CANCELLED', updated_at = ?
                        WHERE challenge_id = ? AND invitation_status = 'INVITED'
                    """, (now_str, challenge_id))
                else:
                    conn.execute("UPDATE friendly_challenges SET updated_at = ? WHERE id = ?", (now_str, challenge_id))

            conn.commit()
            return True

        # Cancel entire challenge
        conn.execute("""
            UPDATE friendly_challenges
            SET status = 'CANCELLED', updated_at = ?
            WHERE id = ?
        """, (now_str, challenge_id))

        conn.execute("""
            UPDATE challenge_participants
            SET invitation_status = 'CANCELLED', result = 'CANCELLED', updated_at = ?
            WHERE challenge_id = ? AND invitation_status = 'INVITED'
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


def _sanitize_public_run_record(run_dict):
    """
    Sanitizes run record for public/challenge views, ensuring GPS coordinates,
    route data, and private location details are strictly excluded.
    """
    raw_dist = run_dict.get("distance_km")
    try:
        dist_val = round(float(raw_dist or 0.0), 2)
    except (ValueError, TypeError):
        dist_val = 0.0

    raw_time = run_dict.get("time_min")
    try:
        time_val = round(float(raw_time or 0.0), 1)
    except (ValueError, TypeError):
        time_val = 0.0

    raw_pace = run_dict.get("pace")
    pace_val = None
    if raw_pace is not None:
        try:
            pace_val = round(float(raw_pace), 2)
        except (ValueError, TypeError):
            pace_val = str(raw_pace)

    raw_cals = run_dict.get("calories")
    try:
        cals_val = round(float(raw_cals or 0.0), 1)
    except (ValueError, TypeError):
        cals_val = 0.0

    return {
        "id": run_dict.get("id"),
        "distance_km": dist_val,
        "time_min": time_val,
        "pace": pace_val,
        "calories": cals_val,
        "run_type": run_dict.get("run_type") or "easy",
        "date": str(run_dict.get("date") or "")[:19],
        "local_date": run_dict.get("local_date") or str(run_dict.get("date") or "")[:10]
    }


def calculate_participant_score(conn, user_id, challenge_type, start_date, end_date, tz_name="UTC"):
    """Fetches eligible runs, sanitizes public details, and calculates deterministic score for a participant."""
    raw_runs = get_eligible_runs(conn, user_id, start_date, end_date, tz_name)
    score, unit = calculate_score(raw_runs, challenge_type)
    sanitized_runs = [_sanitize_public_run_record(r) for r in raw_runs]
    return score, unit, sanitized_runs


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

        if chal.get("challenge_mode") == "GROUP":
            participants_rows = conn.execute("""
                SELECT cp.user_id, cp.invitation_status, cp.final_score, cp.rank, cp.result,
                       u.username, u.display_name, u.profile_emoji
                FROM challenge_participants cp
                JOIN users u ON cp.user_id = u.id
                WHERE cp.challenge_id = ?
            """, (challenge_id,)).fetchall()

            leaderboard = []
            total_active_score = 0.0
            for r in participants_rows:
                u_id = r["user_id"]
                score, unit, runs = calculate_participant_score(
                    conn, u_id, chal["challenge_type"],
                    chal["start_date"], chal["end_date"], chal["challenge_timezone"]
                )
                inv_stat = r["invitation_status"] or "ACCEPTED"
                if inv_stat == "ACCEPTED":
                    total_active_score += score
                leaderboard.append({
                    "user_id": u_id,
                    "username": r["username"],
                    "display_name": (r["display_name"] or r["username"]),
                    "profile_emoji": r["profile_emoji"] or "🏃",
                    "score": score,
                    "display_score": round(score, 2) if unit == "km" else int(score),
                    "score_unit": unit,
                    "invitation_status": inv_stat,
                    "qualifying_runs": runs,
                    "qualifying_runs_count": len(runs),
                    "result": r["result"] or "PENDING"
                })

            accepted_list = [p for p in leaderboard if p["invitation_status"] == "ACCEPTED"]
            other_list = [p for p in leaderboard if p["invitation_status"] != "ACCEPTED"]
            accepted_list.sort(key=lambda x: x["score"], reverse=True)

            for i, p in enumerate(accepted_list):
                if i > 0:
                    prev = accepted_list[i - 1]
                    if abs(p["score"] - prev["score"]) <= 1e-5:
                        p["rank"] = prev["rank"]
                    else:
                        p["rank"] = i + 1
                else:
                    p["rank"] = 1

                if total_active_score > 0:
                    p["ratio"] = round((p["score"] / total_active_score) * 100, 1)
                else:
                    p["ratio"] = round(100.0 / max(len(accepted_list), 1), 1)

            for p in other_list:
                p["rank"] = None
                p["ratio"] = 0.0

            sorted_leaderboard = accepted_list + other_list
            top_accepted = [p for p in accepted_list if p.get("rank") == 1]
            is_tied = (len(top_accepted) > 1)
            leader_id = top_accepted[0]["user_id"] if len(top_accepted) == 1 else None
            time_remaining = calculate_time_remaining(chal["start_date"], chal["end_date"], chal["challenge_timezone"])

            challenger_data = next((p for p in sorted_leaderboard if p["user_id"] == chal["challenger_id"]), None)
            opponents_data = [p for p in sorted_leaderboard if p["user_id"] != chal["challenger_id"]]

            return {
                "challenge": chal,
                "challenge_mode": "GROUP",
                "score_unit": unit if 'unit' in locals() else SCORE_UNITS.get(chal["challenge_type"], "km"),
                "leader_id": leader_id,
                "is_tied": is_tied,
                "leaders": [p["user_id"] for p in top_accepted],
                "time_remaining": time_remaining,
                "leaderboard": sorted_leaderboard,
                "total_participants": len(participants_rows),
                "accepted_count": len(accepted_list),
                "challenger": challenger_data,
                "opponents": opponents_data,
                "opponent": opponents_data[0] if opponents_data else None,
                "ratio_challenger": challenger_data.get("ratio", 0.0) if challenger_data else 0.0,
                "ratio_opponent": opponents_data[0].get("ratio", 0.0) if opponents_data else 0.0,
            }

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

        if chal.get("challenge_mode") == "GROUP":
            # Group challenge finalization
            participants_rows = conn.execute("""
                SELECT cp.user_id, cp.invitation_status
                FROM challenge_participants cp
                WHERE cp.challenge_id = ? AND cp.invitation_status = 'ACCEPTED'
            """, (challenge_id,)).fetchall()

            if len(participants_rows) < 2:
                # Under flexible threshold, if fewer than 2 accepted by completion, cancel
                conn.execute("""
                    UPDATE friendly_challenges
                    SET status = 'CANCELLED', completed_at = ?, updated_at = ?
                    WHERE id = ?
                """, (now_str, now_str, challenge_id))
                conn.commit()
                chal["status"] = "CANCELLED"
                return chal

            # Compute scores for all accepted participants
            scores = []
            for r in participants_rows:
                u_id = r["user_id"]
                score, unit, _ = calculate_participant_score(
                    conn, u_id, chal["challenge_type"],
                    chal["start_date"], chal["end_date"], chal["challenge_timezone"]
                )
                scores.append({"user_id": u_id, "score": score})

            scores.sort(key=lambda x: x["score"], reverse=True)

            # Assign ranks with tie handling
            for i, item in enumerate(scores):
                if i > 0:
                    prev = scores[i - 1]
                    if abs(item["score"] - prev["score"]) <= 1e-5:
                        item["rank"] = prev["rank"]
                    else:
                        item["rank"] = i + 1
                else:
                    item["rank"] = 1

            top_rankers = [s for s in scores if s["rank"] == 1]
            top_score = top_rankers[0]["score"] if top_rankers else 0.0

            # Unique first-place participant wins; a tie for first results in a draw and no medal
            if len(top_rankers) == 1 and top_score > 0:
                result_type = "WIN"
                winner_id = top_rankers[0]["user_id"]
                winner_ids = [winner_id]
            else:
                result_type = "DRAW"
                winner_id = None
                winner_ids = []

            # Update each participant
            for s in scores:
                if winner_id:
                    p_res = "WIN" if s["user_id"] == winner_id else "LOSS"
                else:
                    p_res = "DRAW" if s["rank"] == 1 else "LOSS"
                conn.execute("""
                    UPDATE challenge_participants
                    SET final_score = ?, rank = ?, result = ?, updated_at = ?
                    WHERE challenge_id = ? AND user_id = ?
                """, (s["score"], s["rank"], p_res, now_str, challenge_id, s["user_id"]))

            # Set non-accepted participants' rank to NULL and result to DECLINED/EXPIRED
            conn.execute("""
                UPDATE challenge_participants
                SET result = CASE WHEN invitation_status = 'REJECTED' THEN 'DECLINED' ELSE 'EXPIRED' END,
                    updated_at = ?
                WHERE challenge_id = ? AND invitation_status != 'ACCEPTED'
            """, (now_str, challenge_id))

            cur = conn.execute("""
                UPDATE friendly_challenges
                SET status = 'COMPLETED', completed_at = ?, winner_id = ?, result_type = ?, updated_at = ?
                WHERE id = ? AND status = 'ACCEPTED'
            """, (now_str, winner_id, result_type, now_str, challenge_id))
            if cur.rowcount == 0:
                chal_done = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
                return dict(chal_done) if chal_done else chal

            # Awards: Only unique 1st place winner with score > 0 receives 1 medal.
            # Draws and non-winners receive NO medal.
            if winner_id:
                has_award = conn.execute(
                    "SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?",
                    (challenge_id, winner_id)
                ).fetchone()
                if not has_award:
                    conn.execute("""
                        INSERT INTO challenge_awards (challenge_id, user_id, award_type, rank, awarded_at)
                        VALUES (?, ?, 'FRIENDLY_CHALLENGE_WIN', 1, ?)
                    """, (challenge_id, winner_id, now_str))
            else:
                conn.execute("DELETE FROM challenge_awards WHERE challenge_id = ?", (challenge_id,))

            # Activity log
            meta = json.dumps({
                "challenge_mode": "GROUP",
                "winner_id": winner_id,
                "winner_ids": winner_ids,
                "result_type": result_type,
                "participants_count": len(scores)
            })
            conn.execute("""
                INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, metadata, created_at)
                VALUES (?, ?, 'COMPLETED', ?, ?)
            """, (challenge_id, winner_id or chal["challenger_id"], meta, now_str))

            # Notifications
            chal_title = chal.get("title") or "Group Challenge"
            try:
                for s in scores:
                    u_id = s["user_id"]
                    if winner_id and u_id == winner_id:
                        _send_challenge_notif(
                            conn, u_id, "Group Victory! 🏆",
                            f"You took 1st place in the {chal_title} group challenge! Friendly Challenges medal awarded."
                        )
                    elif result_type == "DRAW":
                        _send_challenge_notif(
                            conn, u_id, "Challenge Completed",
                            f"The {chal_title} group challenge ended in a tie!"
                        )
                    else:
                        _send_challenge_notif(
                            conn, u_id, "Challenge Completed",
                            f"The {chal_title} group challenge completed! You finished #{s['rank']}."
                        )
            except Exception as n_err:
                print(f"[RunRush] Group challenge notification warning: {n_err}")

            conn.commit()
            chal["status"] = "COMPLETED"
            chal["winner_id"] = winner_id
            chal["result_type"] = result_type
            chal["completed_at"] = now_str
            return chal

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

        # Update challenge atomically
        cur = conn.execute("""
            UPDATE friendly_challenges
            SET status = 'COMPLETED', completed_at = ?, winner_id = ?, result_type = ?, updated_at = ?
            WHERE id = ? AND status = 'ACCEPTED'
        """, (now_str, winner_id, result_type, now_str, challenge_id))
        if cur.rowcount == 0:
            chal_done = conn.execute("SELECT * FROM friendly_challenges WHERE id = ?", (challenge_id,)).fetchone()
            return dict(chal_done) if chal_done else chal

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

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if chal.get("challenge_mode") == "GROUP":
            # Group challenge recalibration
            participants_rows = conn.execute("""
                SELECT cp.user_id, cp.invitation_status
                FROM challenge_participants cp
                WHERE cp.challenge_id = ? AND cp.invitation_status = 'ACCEPTED'
            """, (challenge_id,)).fetchall()

            scores = []
            for r in participants_rows:
                u_id = r["user_id"]
                score, unit, _ = calculate_participant_score(
                    conn, u_id, chal["challenge_type"],
                    chal["start_date"], chal["end_date"], chal["challenge_timezone"]
                )
                scores.append({"user_id": u_id, "score": score})

            scores.sort(key=lambda x: x["score"], reverse=True)

            for i, item in enumerate(scores):
                if i > 0:
                    prev = scores[i - 1]
                    if abs(item["score"] - prev["score"]) <= 1e-5:
                        item["rank"] = prev["rank"]
                    else:
                        item["rank"] = i + 1
                else:
                    item["rank"] = 1

            top_rankers = [s for s in scores if s["rank"] == 1]
            top_score = top_rankers[0]["score"] if top_rankers else 0.0

            if len(top_rankers) == 1 and top_score > 0:
                result_type = "WIN"
                winner_id = top_rankers[0]["user_id"]
                winner_ids = [winner_id]
            else:
                result_type = "DRAW"
                winner_id = None
                winner_ids = []

            for s in scores:
                if winner_id:
                    p_res = "WIN" if s["user_id"] == winner_id else "LOSS"
                else:
                    p_res = "DRAW" if s["rank"] == 1 else "LOSS"
                conn.execute("""
                    UPDATE challenge_participants
                    SET final_score = ?, rank = ?, result = ?, updated_at = ?
                    WHERE challenge_id = ? AND user_id = ?
                """, (s["score"], s["rank"], p_res, now_str, challenge_id, s["user_id"]))

            conn.execute("""
                UPDATE friendly_challenges
                SET winner_id = ?, result_type = ?, updated_at = ?
                WHERE id = ?
            """, (winner_id, result_type, now_str, challenge_id))

            # Reconcile awards: Only unique winner receives 1 medal
            if winner_id:
                conn.execute(
                    "DELETE FROM challenge_awards WHERE challenge_id = ? AND user_id != ?",
                    (challenge_id, winner_id)
                )
                has_award = conn.execute(
                    "SELECT 1 FROM challenge_awards WHERE challenge_id = ? AND user_id = ?",
                    (challenge_id, winner_id)
                ).fetchone()
                if not has_award:
                    conn.execute("""
                        INSERT INTO challenge_awards (challenge_id, user_id, award_type, rank, awarded_at)
                        VALUES (?, ?, 'FRIENDLY_CHALLENGE_WIN', 1, ?)
                    """, (challenge_id, winner_id, now_str))
            else:
                conn.execute("DELETE FROM challenge_awards WHERE challenge_id = ?", (challenge_id,))

            # Activity log
            meta = json.dumps({
                "challenge_mode": "GROUP",
                "old_winner_id": chal.get("winner_id"),
                "new_winner_id": winner_id,
                "old_result_type": chal.get("result_type"),
                "new_result_type": result_type
            })
            conn.execute("""
                INSERT INTO challenge_activity (challenge_id, actor_id, activity_type, metadata, created_at)
                VALUES (?, ?, 'RECALIBRATED', ?, ?)
            """, (challenge_id, winner_id or chal["challenger_id"], meta, now_str))

            conn.commit()
            return True

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
            SELECT DISTINCT fc.id FROM friendly_challenges fc
            JOIN challenge_participants cp ON fc.id = cp.challenge_id
            WHERE cp.user_id = ?
              AND fc.status = 'COMPLETED'
              AND fc.start_date <= ? AND fc.end_date >= ?
        """, (user_id, date_clean, date_clean)).fetchall()

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

        # Pending incoming invitations count across both 1v1 and group challenges
        inv_row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM challenge_participants cp
            JOIN friendly_challenges fc ON cp.challenge_id = fc.id
            WHERE cp.user_id = ? AND cp.invitation_status = 'INVITED' AND fc.status = 'INVITED'
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
            f"Won {medal_count} Friendly Challenge{'s' if medal_count != 1 else ''}."
            if is_earned
            else "Win a Friendly Challenge against other runners to unlock this medal."
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

