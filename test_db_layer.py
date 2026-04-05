"""
Smoke test for the RunRush database abstraction layer.
Tests that db.py works correctly with SQLite (the local dev database).

Usage:
    python test_db_layer.py
"""

import os
import sys

# Force SQLite mode for testing
os.environ["DATABASE_URL"] = "sqlite:///test_smoke.db"

# Remove stale test DB if it exists
if os.path.exists("test_smoke.db"):
    os.remove("test_smoke.db")

from db import get_db, IntegrityError, USE_PG


def test_connection():
    """Test that get_db() returns a working connection."""
    print("1. Testing connection... ", end="")
    conn = get_db()
    assert conn is not None
    conn.close()
    print("✓")


def test_create_table():
    """Test CREATE TABLE + INSERT + SELECT."""
    print("2. Testing create/insert/select... ", end="")
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            score REAL DEFAULT 0.0
        )
    """)

    conn.execute(
        "INSERT INTO test_users (name, score) VALUES (?, ?)",
        ("alice", 42.5)
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM test_users WHERE name = ?",
        ("alice",)
    ).fetchone()

    assert row is not None
    assert row["name"] == "alice"
    assert row["score"] == 42.5
    conn.close()
    print("✓")


def test_returning():
    """Test INSERT ... RETURNING id."""
    print("3. Testing RETURNING id... ", end="")
    conn = get_db()

    row = conn.execute(
        "INSERT INTO test_users (name, score) VALUES (?, ?) RETURNING id",
        ("bob", 99.0)
    ).fetchone()

    assert row is not None
    new_id = row["id"] if isinstance(row, dict) else row[0]
    assert isinstance(new_id, int)
    assert new_id > 0
    conn.commit()
    conn.close()
    print(f"✓ (id={new_id})")


def test_integrity_error():
    """Test that IntegrityError is raised for duplicate unique values."""
    print("4. Testing IntegrityError... ", end="")
    conn = get_db()

    try:
        conn.execute(
            "INSERT INTO test_users (name, score) VALUES (?, ?)",
            ("alice", 0.0)  # duplicate name
        )
        conn.commit()
        print("✗ FAILED (no error raised)")
        conn.close()
        return False
    except IntegrityError:
        conn.close()
        print("✓")
        return True


def test_fetchall():
    """Test fetchall returns multiple rows."""
    print("5. Testing fetchall... ", end="")
    conn = get_db()

    rows = conn.execute("SELECT * FROM test_users ORDER BY name").fetchall()
    assert len(rows) == 2  # alice + bob
    assert rows[0]["name"] == "alice"
    assert rows[1]["name"] == "bob"
    conn.close()
    print(f"✓ ({len(rows)} rows)")


def test_placeholder_conversion():
    """Test that ? placeholders work (critical for PostgreSQL mode)."""
    print("6. Testing placeholder handling... ", end="")
    conn = get_db()

    # Multiple ? in one query
    rows = conn.execute(
        "SELECT * FROM test_users WHERE score > ? AND score < ?",
        (10.0, 100.0)
    ).fetchall()

    assert len(rows) == 2  # alice=42.5, bob=99.0
    conn.close()
    print("✓")


def cleanup():
    """Remove test database."""
    if os.path.exists("test_smoke.db"):
        os.remove("test_smoke.db")


def main():
    print("=" * 40)
    print("RunRush DB Layer Smoke Tests")
    print(f"Mode: {'PostgreSQL' if USE_PG else 'SQLite'}")
    print("=" * 40 + "\n")

    tests = [
        test_connection,
        test_create_table,
        test_returning,
        test_integrity_error,
        test_fetchall,
        test_placeholder_conversion,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            if result is not False:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed += 1

    cleanup()

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 40)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
