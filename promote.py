from app import app
import db

with app.app_context():
    conn = db.get_db()
    conn.execute("UPDATE users SET role = 'admin' WHERE username = 'Yajat'")
    conn.commit()
    print("User 'Yajat' has been promoted to admin.")
