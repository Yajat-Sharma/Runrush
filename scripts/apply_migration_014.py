"""Apply migration 014: Add run_routes table for GPS route storage."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db

def apply():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_routes (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            route_json TEXT NOT NULL,
            total_distance_km REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_run_routes_run_id ON run_routes(run_id)")
    conn.commit()
    conn.close()
    print("Migration 014 applied successfully.")

if __name__ == "__main__":
    apply()
