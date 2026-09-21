import os
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_QnL41MkIWEzZ@ep-dark-term-b5ajazfp-pooler.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require'

from app import app
from db import get_db

with app.test_client() as client:
    # 1. Register user 'Yajat'
    print("Registering Yajat...")
    resp = client.post('/register', data={
        'username': 'Yajat',
        'pin': '123456',
        'display_name': 'Yajat',
        'height': '175',
        'weight': '70'
    }, follow_redirects=True)
    print("Register status:", resp.status_code)
    
    # Check if Yajat exists
    with app.app_context():
        u = get_db().execute("SELECT * FROM users WHERE username='Yajat'").fetchone()
        print("User Yajat in DB:", bool(u))

    # Log in
    client.post('/login', data={'username': 'Yajat', 'pin': '123456'}, follow_redirects=True)

    # 2. Test APIs
    endpoints = [
        '/api/monthly-progress',
        '/api/pet-status',
        '/api/badges',
        '/api/user/Yajat/public-profile',
        '/api/user/Yajat/heatmap',
        '/api/analytics/insights'
    ]
    
    api_fail = False
    for ep in endpoints:
        r = client.get(ep)
        print(f"API {ep}: {r.status_code}")
        if r.status_code >= 400:
            api_fail = True

    # 3. Test UI
    ui_endpoints = [
        '/',
        '/dashboard',
        '/social',
        '/settings',
        '/profile'
    ]
    ui_fail = False
    for ep in ui_endpoints:
        r = client.get(ep)
        print(f"UI {ep}: {r.status_code}")
        if r.status_code >= 400:
            ui_fail = True
            
    # Check public profile text
    r = client.get('/user/Yajat')
    if b'Profile not found' in r.data:
        print("ERROR: Profile not found shown for valid profile!")
        ui_fail = True
    else:
        print("Public profile loads correctly without 'Profile not found'")

    print("\nSUMMARY:")
    print("API health:", "PASS" if not api_fail else "FAIL")
    print("Live UI smoke test:", "PASS" if not ui_fail else "FAIL")
