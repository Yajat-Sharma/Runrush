import os
os.environ['DATABASE_URL'] = 'sqlite:///runs.db'
import sys
sys.modules['psycopg2'] = type('Mock', (), {})
sys.modules['psycopg2.extras'] = type('Mock', (), {})
import app
app.app.config['TESTING'] = True
client = app.app.test_client()
with client.session_transaction() as sess: sess['user_id'] = 1
try:
    r = client.get('/api/badges')
    print('STATUS:', r.status_code)
    print('BODY:', r.data)
except Exception as e:
    import traceback; traceback.print_exc()
