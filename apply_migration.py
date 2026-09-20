from app import app
import db
with app.app_context():
    conn = db.get_db()
    conn.execute("ALTER TABLE users ADD COLUMN profile_emoji TEXT DEFAULT '🏃🏻'")
    conn.commit()
    print('Migration applied successfully!')
