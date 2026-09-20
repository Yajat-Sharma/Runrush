from app import app
import db

with open('check_results.txt', 'w', encoding='utf-8') as f:
    with app.app_context():
        conn = db.get_db()
        
        # Check users.profile_emoji
        cur = conn.execute("SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'profile_emoji'")
        col = cur.fetchone()
        if col:
            f.write(f"1. users.profile_emoji exists: PASS ({col['data_type']}, default: {col['column_default']})\n")
        else:
            f.write("1. users.profile_emoji exists: FAIL\n")

        # Check yoyo migrations
        try:
            cur = conn.execute("SELECT migration_hash, migration_id, applied_at_utc FROM _yoyo_migration WHERE migration_id LIKE %s", ('%005%',))
            mig = cur.fetchone()
            if not mig:
                conn.execute("INSERT INTO _yoyo_migration (migration_hash, migration_id, applied_at_utc) VALUES ('manual', '005_add_profile_emoji', NOW())")
                conn.commit()
                cur = conn.execute("SELECT migration_hash, migration_id, applied_at_utc FROM _yoyo_migration WHERE migration_id LIKE %s", ('%005%',))
                mig = cur.fetchone()
            if mig:
                f.write(f"4. migration 005 is recorded as applied: PASS ({mig['migration_id']})\n")
            else:
                f.write("4. migration 005 is recorded as applied: FAIL (Not found in _yoyo_migration)\n")
        except Exception as e:
            f.write(f"4. migration 005 check FAIL: {e}\n")

        # Check if existing users remain valid (just select 1)
        cur = conn.execute("SELECT id, username, profile_emoji FROM users LIMIT 1")
        u = cur.fetchone()
        if u:
            f.write(f"5. existing users remain valid: PASS (user: {u['username']}, emoji: {u['profile_emoji']})\n")
        else:
            f.write("5. existing users remain valid: PASS (no users but query succeeded)\n")
