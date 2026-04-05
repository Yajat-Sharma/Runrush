"""
Database abstraction layer for RunRush.
Supports both SQLite (local dev) and PostgreSQL (production).
Controlled by the DATABASE_URL environment variable.

Design: wraps the psycopg2 connection/cursor to behave like sqlite3,
so all existing conn.execute() / cursor.fetchone() calls in app.py
work without modification.
"""

import os
import sqlite3

# --------------- Configuration ---------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///runs.db")

# Render sometimes provides postgres:// instead of postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = DATABASE_URL.startswith("postgresql")

if USE_PG:
    import psycopg2
    import psycopg2.extras


# --------------- Unified IntegrityError ---------------

if USE_PG:
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


# --------------- PostgreSQL Wrappers ---------------

class PgCursorWrapper:
    """Wraps a psycopg2 RealDictCursor to behave like sqlite3.Cursor."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        # psycopg2 doesn't support lastrowid reliably
        # Use RETURNING id in your INSERT queries instead
        return None

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()


class PgConnectionWrapper:
    """
    Wraps a psycopg2 connection to behave like sqlite3.Connection.
    - Auto-converts ? placeholders to %s
    - Returns dict-like rows via RealDictCursor
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql, params=None):
        """Execute SQL, auto-converting ? → %s for PostgreSQL."""
        converted_sql = sql.replace("?", "%s")
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(converted_sql, params or ())
        return PgCursorWrapper(cursor)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def rollback(self):
        self._conn.rollback()


# --------------- Connection Factory ---------------

def get_db():
    """
    Returns a database connection.
    - SQLite:  native sqlite3 connection with Row factory
    - PostgreSQL: PgConnectionWrapper (same API as sqlite3)
    """
    if USE_PG:
        raw_conn = psycopg2.connect(DATABASE_URL)
        return PgConnectionWrapper(raw_conn)
    else:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
