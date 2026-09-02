import app; client = app.app.test_client();
with client.session_transaction() as sess: sess['user_id'] = 1
r = client.get('/api/badges')
print('STATUS:', r.status_code)
print('BODY:', r.data.decode('utf-8'))
