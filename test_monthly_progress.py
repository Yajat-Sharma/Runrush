
from app import app
from db import get_db
import os
import psycopg2

os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_Bp2ZcLuge8HC@ep-rough-unit-awe9g4r7-pooler.c-12.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require'

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 2 # Yajat
    
    resp = client.get('/api/monthly-progress')
    print('Status:', resp.status_code)
    print('Data:', resp.data.decode())

