import app
from db import get_db

with app.app.app_context():
    try:
        conn = get_db()
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        user_id = 1
        goal_type = 'custom'
        target_distance_km = 42.0
        target_date = "2026-11-02"
        days_per_week = 3
        
        conn.execute(
            """
            INSERT INTO user_goals 
            (user_id, goal_type, target_distance_km, target_date, days_per_week, status, created_at, dashboard_pinned)
            VALUES (?, ?, ?, ?, ?, 'active', ?, 0)
            """,
            (user_id, goal_type, target_distance_km, target_date, days_per_week, now_str)
        )
        conn.commit()
        conn.close()
        print("Success")
    except Exception as e:
        import traceback
        traceback.print_exc()
