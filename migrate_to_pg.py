"""
SQLite → PostgreSQL Data Migration Script for RunRush.

Reads all data from the local runs.db (SQLite) and inserts it into a
PostgreSQL database specified by the DATABASE_URL environment variable.

Usage:
    set DATABASE_URL=postgresql://user:pass@host:5432/dbname
    python migrate_to_pg.py

Safety:
    - Read-only on SQLite (source)
    - Idempotent: skips rows that already exist (ON CONFLICT DO NOTHING)
    - Resets PostgreSQL SERIAL sequences to match max IDs
"""

import os
import sys
import sqlite3

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 is not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


# ---------- Configuration ----------

SQLITE_PATH = "runs.db"
PG_URL = os.environ.get("DATABASE_URL", "")

if PG_URL.startswith("postgres://"):
    PG_URL = PG_URL.replace("postgres://", "postgresql://", 1)

if not PG_URL.startswith("postgresql"):
    print("ERROR: DATABASE_URL must be a PostgreSQL URL.")
    print("Example: set DATABASE_URL=postgresql://user:pass@host:5432/dbname")
    sys.exit(1)


# ---------- Helpers ----------

def get_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_pg():
    return psycopg2.connect(PG_URL)


def table_exists_sqlite(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row is not None


def migrate_table(sqlite_conn, pg_conn, table_name, columns):
    """
    Migrate a single table from SQLite to PostgreSQL.
    
    Args:
        table_name: Name of the table
        columns: List of column names to migrate
    
    Returns:
        Number of rows migrated
    """
    if not table_exists_sqlite(sqlite_conn, table_name):
        print(f"  ⚠ Table '{table_name}' not found in SQLite — skipping")
        return 0

    # Read from SQLite
    col_str = ", ".join(columns)
    rows = sqlite_conn.execute(f"SELECT {col_str} FROM {table_name}").fetchall()

    if not rows:
        print(f"  ⚠ Table '{table_name}' is empty — skipping")
        return 0

    # Build INSERT with ON CONFLICT DO NOTHING
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"""
        INSERT INTO {table_name} ({col_str})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    pg_cur = pg_conn.cursor()
    count = 0
    for row in rows:
        values = tuple(row[col] for col in columns)
        try:
            pg_cur.execute(insert_sql, values)
            count += 1
        except Exception as e:
            print(f"  ✗ Error inserting into {table_name}: {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()
    pg_cur.close()
    return count


def reset_sequence(pg_conn, table_name, id_column="id"):
    """Reset PostgreSQL SERIAL sequence to match max ID in the table."""
    pg_cur = pg_conn.cursor()
    pg_cur.execute(f"SELECT MAX({id_column}) FROM {table_name}")
    max_id = pg_cur.fetchone()[0]

    if max_id is not None:
        seq_name = f"{table_name}_{id_column}_seq"
        pg_cur.execute(f"SELECT setval('{seq_name}', {max_id})")
        print(f"  ↻ Reset sequence '{seq_name}' to {max_id}")

    pg_conn.commit()
    pg_cur.close()


# ---------- Table Definitions ----------

TABLES = [
    {
        "name": "users",
        "columns": [
            "id", "username", "pin", "display_name", "weight",
            "weekly_goal_km", "theme", "height", "last_login",
            "role", "status"
        ]
    },
    {
        "name": "runs",
        "columns": [
            "id", "user_id", "date", "distance_km", "time_min",
            "pace", "calories", "created_at", "insight"
        ]
    },
    {
        "name": "user_stats",
        "columns": [
            "id", "user_id", "total_distance_km", "current_streak",
            "best_streak", "last_activity_date", "updated_at"
        ]
    },
    {
        "name": "badges",
        "columns": [
            "id", "key", "name", "description", "icon_url",
            "criteria_type", "criteria_value"
        ]
    },
    {
        "name": "user_badges",
        "columns": [
            "id", "user_id", "badge_key", "unlocked_at", "activity_id"
        ]
    },
    {
        "name": "activity_logs",
        "columns": [
            "id", "user_id", "action", "details", "timestamp"
        ]
    },
    {
        "name": "edit_history",
        "columns": [
            "id", "run_id", "user_id", "field_name",
            "old_value", "new_value", "edited_at"
        ]
    },
    {
        "name": "admin_notes",
        "columns": [
            "id", "target_user_id", "author_id", "note", "timestamp"
        ]
    },
]


# ---------- Main ----------

def main():
    print("=" * 50)
    print("RunRush: SQLite → PostgreSQL Migration")
    print("=" * 50)
    print(f"\nSource:  {SQLITE_PATH}")
    print(f"Target:  {PG_URL[:40]}...")
    print()

    # Verify SQLite file exists
    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite database '{SQLITE_PATH}' not found.")
        sys.exit(1)

    # Connect
    sqlite_conn = get_sqlite()
    pg_conn = get_pg()

    print("✓ Connected to both databases\n")

    # First, ensure tables exist in PostgreSQL
    # (init_db should have run already, but let's be safe)
    print("Creating tables if they don't exist...")
    from app import init_db
    # Force USE_PG for init
    import db as db_module
    old_url = db_module.DATABASE_URL
    db_module.DATABASE_URL = PG_URL
    db_module.USE_PG = True
    # Re-import psycopg2 stuff if needed
    try:
        init_db()
        print("✓ Tables verified\n")
    except Exception as e:
        print(f"⚠ init_db warning: {e}")
    finally:
        db_module.DATABASE_URL = old_url

    # Migrate each table
    print("Migrating data...\n")
    summary = {}

    for table_def in TABLES:
        name = table_def["name"]
        columns = table_def["columns"]
        print(f"  📋 {name}...")
        count = migrate_table(sqlite_conn, pg_conn, name, columns)
        summary[name] = count
        print(f"    ✓ {count} rows migrated")

    # Reset sequences
    print("\nResetting sequences...")
    for table_def in TABLES:
        reset_sequence(pg_conn, table_def["name"])

    # Summary
    print("\n" + "=" * 50)
    print("Migration Summary")
    print("=" * 50)
    total = 0
    for name, count in summary.items():
        print(f"  {name:20s} → {count:5d} rows")
        total += count
    print(f"  {'TOTAL':20s} → {total:5d} rows")
    print("\n✅ Migration complete!")

    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
