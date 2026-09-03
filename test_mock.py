import sys; sys.path.insert(0, '.venv/Lib/site-packages'); import psycopg2; import app; app.app.config['TESTING'] = True; client = app.app.test_client();
with client.session_transaction() as sess: sess['user_id'] = 1
r = client.get('/api/badges'); print(r.status_code); print(r.data.decode('utf-8'))
