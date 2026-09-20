
import psycopg2
import sys

db_url = 'postgresql://neondb_owner:npg_8cm0DhaRfqdU@ep-crimson-grass-awj5jv3o-pooler.c-12.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require'

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    cur.execute('SELECT current_database(), current_schema(), current_user, version()')
    row = cur.fetchone()
    print('current_database():', row[0])
    print('current_schema():', row[1])
    print('current_user:', row[2])
    print('version():', row[3])
    
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
    users_cols = [r[0] for r in cur.fetchall()]
    print('\nUsers table exists:', len(users_cols) > 0)
    if users_cols:
        print('username exists:', 'username' in users_cols)
        print('display_name exists:', 'display_name' in users_cols)
        print('profile_emoji exists:', 'profile_emoji' in users_cols)
        
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'monthly_goals'")
    mg_cols = [r[0] for r in cur.fetchall()]
    print('\nMonthly_goals table exists:', len(mg_cols) > 0)
    if mg_cols:
        print('id exists:', 'id' in mg_cols)
        print('user_id exists:', 'user_id' in mg_cols)
        print('year exists:', 'year' in mg_cols)
        print('month exists:', 'month' in mg_cols)
        print('target_km exists:', 'target_km' in mg_cols)
        print('created_at exists:', 'created_at' in mg_cols)
        print('updated_at exists:', 'updated_at' in mg_cols)
        
        cur.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'monthly_goals'::regclass")
        print('\nmonthly_goals constraints:')
        for con in cur.fetchall():
            print(f' - {con[0]}: {con[1]}')
            
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name = '_yoyo_migration'")
    if cur.fetchone():
        cur.execute("SELECT migration_id FROM _yoyo_migration ORDER BY applied_at_utc DESC")
        print('\nyoyo migrations applied:')
        for r in cur.fetchall():
            print(r[0])
    else:
        print('\n_yoyo_migration table does NOT exist')
        
    # Check data for user Yajat
    try:
        cur.execute("SELECT id, username, display_name FROM users WHERE username = 'Yajat'")
        u = cur.fetchone()
        if u:
            print('\nUser Yajat found')
            print('display_name:', u[2])
            print('profile_emoji: ERROR (Column does not exist)')
            
            # Check monthly goals for September 2026
            try:
                cur.execute('SELECT target_km FROM monthly_goals WHERE user_id = %s AND year = 2026 AND month = 9', (u[0],))
                m = cur.fetchone()
                if m:
                    print('monthly_goals for Sep 2026 exists:', m[0])
                else:
                    print('monthly_goals for Sep 2026 DOES NOT exist')
            except Exception as e:
                print('Error reproducing /api/monthly-progress:', e)
                conn.rollback()
        else:
            print('\nUser Yajat NOT found')
    except Exception as e:
        print('Error reproducing /api/user/Yajat/public-profile:', e)
        conn.rollback()
        
        # We still need to reproduce /api/monthly-progress if the first query failed!
        try:
            # We don't have user id because first query failed, so just check if we can query monthly_goals directly
            cur.execute('SELECT target_km FROM monthly_goals LIMIT 1')
            m = cur.fetchone()
            print('monthly_goals table query succeeded. First row:', m)
        except Exception as e:
            print('Error reproducing /api/monthly-progress:', e)
            conn.rollback()
        
    conn.close()
    
except Exception as e:
    print('Exception:', e)

