import os
import sys
import unittest
from datetime import datetime, timedelta

# Ensure we explicitly use STAGING_DATABASE_URL
staging_url = os.environ.get("STAGING_DATABASE_URL")
if not staging_url:
    print("ERROR: STAGING_DATABASE_URL environment variable is required.")
    print("This ensures the smoke test explicitly targets an approved staging database.")
    sys.exit(1)

# Guardrail: Never allow connection to production via smoke test
if "runrush-production" in staging_url.lower() or "prod" in staging_url.lower():
    print("ERROR: STAGING_DATABASE_URL appears to point to production. Smoke test rejected.")
    sys.exit(1)

# Map STAGING_DATABASE_URL safely into the standard configuration
os.environ["DATABASE_URL"] = staging_url
# Provide explicit approval matching the db.py guardrails
os.environ["APPROVED_TEST_DB_URL"] = staging_url

os.environ["FLASK_ENV"] = "production" # Disable sqlite defaults
os.environ["TESTING"] = "1"

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db

class StagingSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def setUp(self):
        import time
        self.username = f'staging_smoke_user_{int(time.time())}'

    def test_end_to_end_smoke(self):
        # 1. Registration
        res = self.client.post('/register', data={
            'username': self.username,
            'pin': '1234'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Logout
        res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Login
        res = self.client.post('/login', data={
            'username': self.username,
            'pin': '1234'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Get User ID
        with self.client.session_transaction() as session:
            user_id = session.get('user_id')
        self.assertIsNotNone(user_id)

        # 2. Onboarding
        res = self.client.post('/onboarding', data={
            'display_name': 'Staging Smoke User',
            'weight': '70.0',
            'experience': 'Beginner',
            'primary_goal': 'Fitness',
            'frequency': '3 times',
            'weekly_goal': '10.0'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 3. Adopt Pace Pet
        res = self.client.post('/api/adopt-pet', json={
            'pet_type': 'dog',
            'pet_name': 'SmokeDog'
        })
        if res.status_code != 200:
            print("Adopt pet failed:", res.get_json())
        self.assertEqual(res.status_code, 200)

        # 4. Create Run (Should update progress, pet, and award badges/challenges)
        run_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'distance': '5.5', # >5.0 km to trigger FIRST_5K badge
            'time': '30',
            'run_type': 'Easy',
            'notes': 'Smoke test run'
        }
        res = self.client.post('/add', data=run_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Run in DB
        with app.app_context():
            from db import get_db
            conn = get_db()
            run_row = conn.execute("SELECT * FROM runs WHERE user_id = ?", (user_id,)).fetchone()
            self.assertIsNotNone(run_row)
            run_id = run_row['id']

        # Check badges
        res = self.client.get('/api/badges')
        self.assertEqual(res.status_code, 200)
        badges = res.get_json()['badges']
        unlocked = [b['key'] for b in badges if b['earned']]
        self.assertIn('FIRST_5K', unlocked)

        # Check challenges
        res = self.client.get('/api/challenges')
        self.assertEqual(res.status_code, 200)
        challenges = res.get_json()['challenges']
        c_20k = next((c for c in challenges if c['key'] == 'MONTHLY_20KM'), None)
        self.assertIsNotNone(c_20k)
        self.assertEqual(c_20k['current_progress'], 5.5)

        # Check Pace Pet
        res = self.client.get('/api/pet-status')
        self.assertEqual(res.status_code, 200)
        pet = res.get_json()
        self.assertEqual(pet['total_km_fed'], 5.5)

        # Edit Run
        res = self.client.post(f'/edit/{run_id}', data={
            'date': datetime.now().strftime('%Y-%m-%d'),
            'distance': '10.5', # Change to 10.5 to trigger FIRST_10K
            'time': '55',
            'run_type': 'Long',
            'notes': 'Edited run'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check badges again
        res = self.client.get('/api/badges')
        badges = res.get_json()['badges']
        unlocked = [b['key'] for b in badges if b['earned']]
        self.assertIn('FIRST_10K', unlocked)

        # Delete Run
        res = self.client.post(f'/delete/{run_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check run deleted
        with app.app_context():
            conn = get_db()
            run_count = conn.execute("SELECT COUNT(*) as c FROM runs WHERE user_id = ?", (user_id,)).fetchone()['c']
            self.assertEqual(run_count, 0)

        # Check that FIRST_10K badge still exists (RESTRICT behavior)
        res = self.client.get('/api/badges')
        badges = res.get_json()['badges']
        unlocked = [b['key'] for b in badges if b['earned']]
        self.assertIn('FIRST_10K', unlocked)

if __name__ == '__main__':
    unittest.main()
