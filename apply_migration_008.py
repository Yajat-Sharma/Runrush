from app import app
import db

# Creates the run_likes table for the Home activity feed.
# Safe to run more than once (CREATE ... IF NOT EXISTS).
with app.app_context():
    conn = db.get_db()
    with open('migrations/008_add_run_likes.sql', 'r', encoding='utf-8') as f:
        script = f.read()

    if hasattr(conn, '_conn'):
        cursor = conn._conn.cursor()
        cursor.execute(script)
        conn._conn.commit()
    else:
        conn.executescript(script)
        conn.commit()

    print('Migration 008 applied successfully! (run_likes table is ready)')
