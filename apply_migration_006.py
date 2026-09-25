from app import app
import db

with app.app_context():
    conn = db.get_db()
    with open('migrations/006_add_notifications.sql', 'r') as f:
        script = f.read()
    
    if hasattr(conn, '_conn'):
        cursor = conn._conn.cursor()
        cursor.execute(script)
        conn._conn.commit()
    else:
        conn.executescript(script)
        conn.commit()
        
    print('Migration 006 applied successfully!')
