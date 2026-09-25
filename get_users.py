from app import app
import db
import json

with app.app_context():
    conn = db.get_db()
    cur = conn.execute("SELECT id, username, role FROM users")
    rows = cur.fetchall() if hasattr(cur, 'fetchall') else cur.fetchall()
    users = [dict(r) for r in rows]
    print(json.dumps(users, indent=2))
