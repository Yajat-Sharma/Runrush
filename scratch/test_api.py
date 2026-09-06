import urllib.request
import json

data = json.dumps({
    "goal_type": "custom",
    "target_distance_km": "42",
    "target_date": "2026-11-02",
    "days_per_week": "3"
}).encode('utf-8')

req = urllib.request.Request("http://127.0.0.1:5000/api/goals", data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as f:
        print(f.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError", e.code)
    print(e.read().decode('utf-8'))
