from app import app, get_db

with app.app_context():
    conn = get_db()
    res = conn.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users';").fetchall()
    print([dict(r) for r in res])
