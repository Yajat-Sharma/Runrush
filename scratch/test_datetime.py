import os
import sys
import datetime
sys.path.insert(0, os.path.abspath('.'))
os.environ["DATABASE_URL"] = "sqlite:///test_reproduce.db"
os.environ["FLASK_ENV"] = "testing"

from app import app
import services.badge_service

# Mock get_user_badges to return datetime objects like psycopg2
def mock_get_user_badges(user_id):
    return [{
        "unlocked_at": datetime.datetime.now(),
        "activity_id": 1,
        "badge_key": "FIRST_5K",
        "name": "First 5K",
        "icon_url": "/static/badges/5k.png"
    }]

services.badge_service.get_user_badges = mock_get_user_badges

client = app.test_client()
with client.session_transaction() as sess:
    sess['user_id'] = 1

res = client.get('/api/badges')
print("STATUS CODE:", res.status_code)
if res.status_code != 200:
    print("ERROR:", res.get_data(as_text=True))
