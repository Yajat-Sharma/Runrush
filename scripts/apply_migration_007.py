"""Apply the monthly_summary_deliveries schema migration to the configured database."""

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
        script = (ROOT / "migrations" / "007_add_monthly_summary_deliveries.sql").read_text(encoding="utf-8")
        if hasattr(conn, "_conn"):
            conn.executescript(script)
        else:
            conn.cursor().execute(script)
            conn.commit()
        print("Migration 007 applied successfully! (monthly_summary_deliveries table is ready)")


if __name__ == "__main__":
    main()
