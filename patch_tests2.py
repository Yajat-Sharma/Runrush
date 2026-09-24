with open('tests/test_google_auth.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_test = '''
def test_google_login_incomplete_user(client, mocker):
    mock_oauth_flow(mocker, 'google_inc', 'inc@example.com')
    
    with client.session_transaction() as sess:
        sess.clear()
        
    response = client.get('/auth/google/callback', follow_redirects=True)
    assert response.status_code == 200
    assert b'WELCOME TO RUNRUSH' in response.data or b'Display Name' in response.data
    
    with client.session_transaction() as sess:
        assert sess['username'] == 'incomplete_google_user'
'''

code += new_test

with open('tests/test_google_auth.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Added incomplete user test.")
