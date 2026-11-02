import requests
import json

# Test the parse-screenshot endpoint with a simple request to see what HTML comes back
url = "http://127.0.0.1:5000/api/parse-screenshot"

# First test without auth to see if we get HTML
try:
    resp = requests.post(url, data={"client_date": "2026-10-23"}, timeout=10)
    print("Status:", resp.status_code)
    print("Headers:", dict(resp.headers))
    print("Body (first 500 chars):", resp.text[:500])
except Exception as e:
    print("Error:", e)

print("\n--- Testing with a fake image file ---")
try:
    import io
    # Create a minimal fake image
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    files = {'file': ('test.png', buf, 'image/png')}
    data = {'client_date': '2026-10-23'}
    resp = requests.post(url, files=files, data=data, timeout=30)
    print("Status:", resp.status_code)
    print("Content-Type:", resp.headers.get('Content-Type'))
    print("Body:", resp.text[:1000])
except Exception as e:
    print("Error:", type(e).__name__, e)
    import traceback
    traceback.print_exc()
