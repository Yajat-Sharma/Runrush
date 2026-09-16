import os
from dotenv import load_dotenv
load_dotenv()

from db import get_db

try:
    conn = get_db()
    
    tables = [
        'users', 'runs', 'user_stats', 'user_weekly_goals', 'user_goals',
        'user_badges', 'badges', 'friends', 'user_challenge_progress',
        'user_dashboard_layout', 'user_pets', 'user_pet_collection',
        'edit_history', 'activity_logs', 'admin_notes', 'pin_resets'
    ]
    
    print('--- Table Counts ---')
    for table in tables:
        try:
            res = conn.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()
            print(f'{table}: {res["c"]}')
        except Exception as e:
            print(f'{table}: DOES NOT EXIST or ERROR ({e})')
            # Rollback in case of aborted transaction error
            try:
                conn.rollback()
            except:
                pass
            
    print('\n--- Users Sample ---')
    try:
        users = conn.execute('SELECT id, username, display_name FROM users ORDER BY id LIMIT 20').fetchall()
        for u in users: print(dict(u))
    except Exception as e: print(e)

    print('\n--- Runs Sample ---')
    try:
        runs = conn.execute('SELECT id, user_id, date, distance_km FROM runs ORDER BY id DESC LIMIT 20').fetchall()
        for r in runs: print(dict(r))
    except Exception as e: print(e)
    
except Exception as e:
    print('Failed to connect:', e)
