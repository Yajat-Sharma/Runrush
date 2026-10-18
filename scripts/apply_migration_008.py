"""Apply the run-likes schema migration to the configured database."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
import db


def main():
    with app.app_context():
        conn = db.get_db()
        script = (ROOT / "migrations" / "008_add_run_likes.sql").read_text(encoding="utf-8")
        if hasattr(conn, "_conn"):
            conn.executescript(script)
        else:
            conn.cursor().execute(script)
            conn.commit()
        print("Migration 008 applied successfully! (run_likes table is ready)")


if __name__ == "__main__":
    main()
