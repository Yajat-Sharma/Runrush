from app import app
import db

# Drops the Pace Pet table (user_pets). Irreversible: deletes all pet data.
# Safe to run more than once (DROP ... IF EXISTS).
with app.app_context():
    conn = db.get_db()
    with open('migrations/009_drop_user_pets.sql', 'r', encoding='utf-8') as f:
        script = f.read()

    if hasattr(conn, '_conn'):
        cursor = conn._conn.cursor()
        cursor.execute(script)
        conn._conn.commit()
    else:
        conn.executescript(script)
        conn.commit()

    print('Migration 009 applied successfully! (user_pets table dropped)')
