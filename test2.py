import os
os.environ['DATABASE_URL'] = 'sqlite:///runs.db'
import app
with app.app.test_request_context():
    app.init_db()
    conn = app.get_db()
    conn.execute('INSERT OR IGNORE INTO users (id, username, pin) VALUES (1, ''test'', ''123'')')
    conn.commit(); conn.close()
    app.session['user_id'] = 1
    try:
        r = app.get_badges()
        print(r.get_json())
    except Exception as e:
        import traceback; traceback.print_exc()
