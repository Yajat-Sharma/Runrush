from flask import Flask, g
import sqlite3
import uuid

app = Flask(__name__)

db_id = str(uuid.uuid4())
db_path = f"file:{db_id}?mode=memory&cache=shared"

def get_db():
    if 'db' not in g:
        print(f"Connecting to {db_path}...")
        g.db = sqlite3.connect(db_path, uri=True)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        print("Closing DB from teardown")
        db.close()

@app.route("/")
def index():
    conn = get_db()
    res = conn.execute("SELECT * FROM users").fetchall()
    return str(res)

with app.app_context():
    keepalive = get_db()
    keepalive.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    keepalive.commit()
    print("Tables created")

    client = app.test_client()
    try:
        res = client.get("/")
        print("Response:", res.data)
    except Exception as e:
        print("Error:", repr(e))
