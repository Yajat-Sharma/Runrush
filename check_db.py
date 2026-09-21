from app import app, get_db
import json

with app.app_context():
    conn = get_db()
    res = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';").fetchall()
    columns = [dict(r)['column_name'] for r in res]
    print("Columns:", columns)
    
    if 'profile_emoji' in columns:
        print("Column exists!")
        users = conn.execute("SELECT username, profile_emoji FROM users").fetchall()
        for u in users:
            print(dict(u)['username'], "has emoji", repr(dict(u).get('profile_emoji')))
    else:
        print("Column DOES NOT EXIST!")
