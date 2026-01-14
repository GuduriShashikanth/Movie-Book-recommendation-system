"""
Test registration with detailed error output
"""
import requests
import json

API_URL = "https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app"

print("Testing User Registration...")
print("="*60)

payload = {
    "email": "testuser123@example.com",
    "password": "testpass123",
    "name": "Test User"
}

print(f"\nPayload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        f"{API_URL}/auth/register",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    try:
        print(f"\nResponse JSON:")
        print(json.dumps(response.json(), indent=2))
    except:
        print(f"\nResponse Text:")
        print(response.text)
        
except Exception as e:
    print(f"\nError: {e}")

print("\n" + "="*60)
print("\nIf you see 500 error, check Koyeb logs:")
print("1. Go to Koyeb dashboard")
print("2. Select your service")
print("3. Click 'Logs' tab")
print("4. Look for Python traceback")
