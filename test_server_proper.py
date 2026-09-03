import os
os.environ['DATABASE_URL'] = 'sqlite:///runs.db'
import app
with app.app.app_context():
    app.init_db()
    conn = app.get_db()
    conn.execute('INSERT OR IGNORE INTO users (id, username, pin) VALUES (1, "test_user", "123")')
    conn.commit()
    conn.close()

client = app.app.test_client()
with client.session_transaction() as sess:
    sess['user_id'] = 1

try:
    res = client.get('/api/badges')
    print('STATUS:', res.status_code)
    print('BODY:', res.get_data(as_text=True))
except Exception as e:
    import traceback; traceback.print_exc()
