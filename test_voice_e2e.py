"""Quick E2E test for voice quick-log endpoint."""
import requests, re

s = requests.Session()

# 1. Hit root to see where we end up
r = s.get("http://127.0.0.1:5000/", allow_redirects=True)
print(f"Root: {r.status_code} url={r.url} len={len(r.text)}")

# 2. Login  
r = s.post("http://127.0.0.1:5000/login", data={"username": "yajat", "pin": "1234"}, allow_redirects=True)
print(f"Login: {r.status_code} url={r.url}")

# 3. Get main page for CSRF
r = s.get("http://127.0.0.1:5000/")
print(f"Home: {r.status_code} len={len(r.text)}")
csrf_match = re.search(r'csrf-token["\s]+content="([^"]+)"', r.text)
csrf_token = csrf_match.group(1) if csrf_match else "NONE"
print(f"CSRF token: {csrf_token[:30]}...")

# 4. Call voice endpoint
r = s.post(
    "http://127.0.0.1:5000/api/voice-quick-log",
    json={"distance": 5, "time_minutes": 28},
    headers={"X-CSRFToken": csrf_token},
)
print(f"Voice API: {r.status_code} {r.text[:300]}")
