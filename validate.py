import psycopg2
conn = psycopg2.connect('postgresql://neondb_owner:npg_QnL41MkIWEzZ@ep-dark-term-b5ajazfp-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require')
cur = conn.cursor()

print('--- TABLES ---')
expected_tables = ['users', 'runs', 'user_stats', 'user_weekly_goals', 'user_goals', 'badges', 'user_badges', 'challenges', 'user_challenge_progress', 'friends', 'user_pets', 'edit_history', 'activity_logs', 'admin_notes', 'pin_resets', 'monthly_goals']
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
actual_tables = [row[0] for row in cur.fetchall()]
found = 0
for t in expected_tables:
    if t in actual_tables:
        found += 1
print(f'Tables found: {found} / 16')
for t in expected_tables:
    if t not in actual_tables:
        print(f'Missing table: {t}')

print('\n--- COLUMNS ---')
for t, cols in [('users', ['username', 'display_name', 'height', 'profile_emoji']), ('monthly_goals', ['id', 'user_id', 'year', 'month', 'target_km', 'created_at', 'updated_at'])]:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (t,))
    actual_cols = [row[0] for row in cur.fetchall()]
    for c in cols:
        print(f'{t}.{c}:', 'PASS' if c in actual_cols else 'FAIL')

print('\n--- CONSTRAINTS ---')
cur.execute("""
SELECT tc.constraint_name, tc.constraint_type, kcu.column_name 
FROM information_schema.table_constraints tc 
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name 
WHERE tc.table_name = 'monthly_goals'
""")
constraints = cur.fetchall()
print('monthly_goals constraints:', constraints)

cur.execute("""
SELECT conname, pg_get_constraintdef(c.oid)
FROM pg_constraint c
JOIN pg_class t ON c.conrelid = t.oid
WHERE t.relname = 'monthly_goals';
""")
print('monthly_goals pg_constraints:', cur.fetchall())

print('\n--- FRESH DB ---')
cur.execute('SELECT COUNT(*) FROM users')
print('Users:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM runs')
print('Runs:', cur.fetchone()[0])
