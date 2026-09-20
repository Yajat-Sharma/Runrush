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
from flask import g, current_app

# --------------- Configuration ---------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///runs.db")

# Render sometimes provides postgres:// instead of postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Clean up malformed query parameters with extra '=' (e.g., ?sslmode=require=)
if "?" in DATABASE_URL:
    base, query = DATABASE_URL.split("?", 1)
    new_query_parts = []
    for part in query.split("&"):
        if part.count("=") > 1:
            key, val = part.split("=", 1)
            val = val.replace("=", "")
            new_query_parts.append(f"{key}={val}")
        else:
            new_query_parts.append(part)
    DATABASE_URL = f"{base}?{'&'.join(new_query_parts)}"

USE_PG = DATABASE_URL.startswith("postgresql")

# Safe boot logging (Phase 4)
print(f"[RunRush DB] Engine: {'PostgreSQL' if USE_PG else 'SQLite'}")
print(f"[RunRush DB] Environment: {os.environ.get('FLASK_ENV', 'development')}")

if USE_PG:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool
    from psycopg2.extensions import register_type, new_type
    
    # Force PostgreSQL to return TIMESTAMP (1114) and TIMESTAMPTZ (1184) as string 
    # to maintain SQLite compatibility for dates
    def _cast_timestamp_to_str(val, cursor):
        return val

    TIMESTAMP_OID = 1114
    TIMESTAMPTZ_OID = 1184
    STRING_TIMESTAMP = new_type((TIMESTAMP_OID, TIMESTAMPTZ_OID), 'STRING_TIMESTAMP', _cast_timestamp_to_str)
    register_type(STRING_TIMESTAMP)

    try:
        pg_pool = psycopg2.pool.SimpleConnectionPool(1, 20, DATABASE_URL)
        print("[RunRush DB] Initialized PostgreSQL connection pool.")
    except Exception as e:
        print(f"[RunRush DB ERROR] Failed to initialize connection pool: {e}")
        pg_pool = None


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

    def __init__(self, pg_conn, pool=None):
        self._conn = pg_conn
        self._pool = pool
        self._closed = False

    def execute(self, sql, params=None):
        """Execute SQL, auto-converting ? → %s for PostgreSQL."""
        converted_sql = sql.replace("?", "%s")
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(converted_sql, params or ())
        return PgCursorWrapper(cursor)

    def commit(self):
        self._conn.commit()

    def close(self, force=False):
        if not force:
            return
        if self._closed:
            return
        self._closed = True
        if self._pool:
            try:
                # Defensively rollback any pending or aborted transactions
                # before returning the connection to the pool.
                self._conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self._conn)
        else:
            self._conn.close()

    def rollback(self):
        self._conn.rollback()


class SqliteConnectionWrapper:
    """Wraps a sqlite3 connection to make close() idempotent."""
    def __init__(self, conn):
        self._conn = conn
        self._closed = False
        
    def execute(self, sql, params=None):
        return self._conn.execute(sql, params or ())
        
    def executescript(self, sql):
        return self._conn.executescript(sql)
        
    def commit(self):
        self._conn.commit()
        
    def close(self, force=False):
        if not force:
            return
        if self._closed:
            return
        self._closed = True
        self._conn.close()
        
    def rollback(self):
        self._conn.rollback()


# --------------- Connection Factory ---------------

def _is_conn_alive(conn):
    """Check if a psycopg2 connection is still usable."""
    try:
        conn.cursor().execute("SELECT 1")
        conn.rollback()  # Don't leave an open transaction from the ping
        return True
    except Exception:
        return False


def get_db():
    """
    Returns a database connection.
    - SQLite:  native sqlite3 connection with Row factory
    - PostgreSQL: PgConnectionWrapper (same API as sqlite3)

    For PostgreSQL, pooled connections are health-checked before being
    returned.  Dead connections (e.g. Neon idle-timeout, SSL drop) are
    discarded and replaced with a fresh connection.
    """
    if 'db' not in g or getattr(g.db, '_closed', False):
        if USE_PG:
            if current_app.config.get('TESTING'):
                approved_url = os.environ.get("APPROVED_TEST_DB_URL")
                if DATABASE_URL != approved_url:
                    raise RuntimeError(
                        f"Test database connection blocked! "
                        f"Production URL detected but not explicitly approved via APPROVED_TEST_DB_URL."
                    )
            
            # Ensure pg_pool exists in namespace even if USE_PG was False at import
            _pool = globals().get('pg_pool', None)
            if _pool:
                raw_conn = _pool.getconn()
                if not _is_conn_alive(raw_conn):
                    # Connection is dead — discard it and open a fresh one
                    try:
                        _pool.putconn(raw_conn, close=True)
                    except Exception:
                        pass
                    raw_conn = psycopg2.connect(DATABASE_URL)
                    g.db = PgConnectionWrapper(raw_conn, pool=None)
                else:
                    g.db = PgConnectionWrapper(raw_conn, pool=_pool)
            else:
                raw_conn = psycopg2.connect(DATABASE_URL)
                g.db = PgConnectionWrapper(raw_conn)
        else:
            db_path = DATABASE_URL.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, uri=True)
            conn.row_factory = sqlite3.Row
            g.db = SqliteConnectionWrapper(conn)

    return g.db

def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close(force=True)
