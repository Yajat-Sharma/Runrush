from app import app, get_db
from extensions import bcrypt
import secrets
from datetime import datetime, timedelta

def _now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

with app.app_context():
    conn = get_db()
    
    # 1. Check if pin_resets exists
    try:
        res = conn.execute("SELECT * FROM pin_resets LIMIT 1").fetchall()
        print("pin_resets exists!")
    except Exception as e:
        print("ERROR selecting from pin_resets:", e)

    # 2. Try the exact logic of generate_and_send_verification_email
    try:
        user_id = 1
        conn.execute(
            "UPDATE pin_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
            (_now_str(), user_id),
        )
        print("UPDATE pin_resets succeeded")
        
        code_int  = secrets.randbelow(900000) + 100000
        code_str  = str(code_int)
        code_hash = bcrypt.generate_password_hash(code_str)
        expires_at = (datetime.utcnow() + timedelta(seconds=900)).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT INTO pin_resets
               (user_id, code_hash, expires_at, attempts, created_at)
               VALUES (?, ?, ?, 0, ?)""",
            (user_id, code_hash.decode('utf-8') if isinstance(code_hash, bytes) else code_hash, expires_at, _now_str()),
        )
        conn.commit()
        print("INSERT INTO pin_resets succeeded")
    except Exception as e:
        print("ERROR modifying pin_resets:", e)

    # 3. Check the users table update
    try:
        conn.execute(
            "UPDATE users SET recovery_email = ?, recovery_email_verified = 0 WHERE id = ?",
            ("test@test.com", user_id)
        )
        conn.commit()
        print("UPDATE users succeeded")
    except Exception as e:
        print("ERROR modifying users:", e)
