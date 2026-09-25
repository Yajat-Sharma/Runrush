from app import app
import db

with app.app_context():
    conn = db.get_db()
    cur = conn.execute("SELECT username FROM users WHERE role='admin'")
    if hasattr(cur, 'fetchall'):
        rows = cur.fetchall()
    else:
        rows = cur.fetchall()
    for row in rows:
        print(row)
