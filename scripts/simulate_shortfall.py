import json
import sqlite3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime, timedelta
import sqlite3
from datetime import datetime, timedelta
import app
from services.goal_service import get_user_goals

def run_simulation():
    # Setup test user and database
    with app.app.app_context():
        conn = app.get_db()
        
        # Create a test user
        username = "simulation_user"
        from models.user import User
        hashed_pin = User.hash_pin("0000")
        conn.execute("INSERT INTO users (username, pin) VALUES (?, ?) ON CONFLICT (username) DO UPDATE SET pin = EXCLUDED.pin", (username, hashed_pin))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        user_id = user["id"]
        
        # Clear existing data for user
        conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_goals WHERE user_id = ?", (user_id,))
        conn.commit()
        
        today = datetime.now()
        # Pretend the goal was created 2 weeks ago
        created_at_date = today - timedelta(weeks=2)
        target_date = today + timedelta(weeks=4) # 4 weeks from now, so 6 weeks total
        
        # Test Half-Marathon (21.1km)
        conn.execute("INSERT INTO user_goals (user_id, goal_type, target_distance_km, target_date, created_at, status, days_per_week) VALUES (?, 'distance', ?, ?, ?, 'active', 3)", (user_id, 21.1, target_date.strftime("%Y-%m-%d"), created_at_date.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        
        # We need a large shortfall to test the 90% cap (18.99km).
        # We'll log perfect runs for the first two weeks in BEFORE, then change it to 0 runs in AFTER to create a MASSIVE shortfall.
        # Week 1 planned = ~5.2, Week 2 planned = ~8.0. Total missing = ~13.2.
        # 13.2 / 4 = 3.3km per week extra.
        # Week 6 original is 18.99. 18.99 + 3.3 = 22.29, which exceeds 18.99! So it should cap at 18.99 and trigger is_at_risk!
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, (today - timedelta(days=10)).strftime("%Y-%m-%d"), 5.2, 30, 6.0, 300, 'long', today.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.execute(
            "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, (today - timedelta(days=3)).strftime("%Y-%m-%d"), 8.0, 45, 6.0, 450, 'long', today.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        
        with open(r"C:\Users\Yajat Sharma\.gemini\antigravity\brain\392e3157-7015-441e-abc7-d5c6f835017f\shortfall_results.md", "w", encoding="utf-8") as f:
            f.write("# Simulated Shortfall Output (90% Cap Test)\n\n")
            f.write("### BEFORE MANUALLY LOGGING SHORTFALL (perfect runs logged)\n```json\n")
            goals = get_user_goals(user_id)
            active_goal = next((g for g in goals if g["status"] == "active"), None) if goals else None
            if active_goal:
                calendar = active_goal["calendar"]
                f.write(json.dumps(calendar, indent=2))
            f.write("\n```\n")
        
        print("\n\n=== LOGGING A MASSIVE SHORTFALL (0 runs logged in elapsed 2 weeks) ===")
        # Delete both perfect runs to create a huge shortfall
        conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
        conn.commit()
        
        with open(r"C:\Users\Yajat Sharma\.gemini\antigravity\brain\392e3157-7015-441e-abc7-d5c6f835017f\shortfall_results.md", "a", encoding="utf-8") as f:
            f.write("\n### AFTER LOGGING MASSIVE SHORTFALL (0 runs logged)\n```json\n")
            goals_after = get_user_goals(user_id)
            active_after = next((g for g in goals_after if g["status"] == "active"), None) if goals_after else None
            if active_after:
                calendar_after = active_after["calendar"]
                f.write(json.dumps(calendar_after, indent=2))
            f.write("\n```\n")
        
if __name__ == '__main__':
    run_simulation()
