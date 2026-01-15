"""
Test script for interactions endpoint
"""
import requests
import json

# Configuration
# BASE_URL = "https://cinelibre-koyeb-cinelibre.koyeb.app"  # Update with your deployed URL
BASE_URL = "http://localhost:8000"  # For local testing

def test_interactions():
    print("=" * 60)
    print("Testing Interactions Endpoint")
    print("=" * 60)
    
    # Step 1: Register/Login to get token
    print("\n1. Logging in...")
    login_data = {
        "email": "testuser123@example.com",
        "password": "testpass123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return
    
    token_data = response.json()
    token = token_data["access_token"]
    user_id = token_data["user"]["id"]
    print(f"✅ Logged in as user {user_id}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Search for a movie to get a valid UUID
    print("\n2. Searching for a movie...")
    search_response = requests.get(
        f"{BASE_URL}/search/semantic",
        params={"q": "action", "type": "movie", "limit": 1}
    )
    
    if search_response.status_code != 200 or not search_response.json().get("results"):
        print(f"❌ Search failed: {search_response.status_code}")
        print(search_response.text)
        return
    
    movie = search_response.json()["results"][0]
    movie_id = movie["id"]
    movie_title = movie["title"]
    print(f"✅ Found movie: {movie_title} (ID: {movie_id})")
    
    # Step 3: Test valid interaction
    print("\n3. Testing VALID interaction (view)...")
    interaction_data = {
        "item_id": movie_id,
        "item_type": "movie",
        "interaction_type": "view"
    }
    
    print(f"   Sending: {json.dumps(interaction_data, indent=2)}")
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200 and response.json().get("success"):
        print("   ✅ Valid interaction tracked successfully")
    else:
        print("   ❌ Valid interaction failed")
    
    # Step 4: Test click interaction
    print("\n4. Testing VALID interaction (click)...")
    interaction_data = {
        "item_id": movie_id,
        "item_type": "movie",
        "interaction_type": "click"
    }
    
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200 and response.json().get("success"):
        print("   ✅ Click interaction tracked successfully")
    else:
        print("   ❌ Click interaction failed")
    
    # Step 5: Test search interaction
    print("\n5. Testing VALID interaction (search)...")
    interaction_data = {
        "item_id": movie_id,
        "item_type": "movie",
        "interaction_type": "search"
    }
    
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200 and response.json().get("success"):
        print("   ✅ Search interaction tracked successfully")
    else:
        print("   ❌ Search interaction failed")
    
    # Step 6: Test invalid item_id (numeric instead of UUID)
    print("\n6. Testing INVALID interaction (numeric item_id)...")
    interaction_data = {
        "item_id": "12345",  # Invalid - not a UUID
        "item_type": "movie",
        "interaction_type": "view"
    }
    
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200 and not response.json().get("success"):
        print("   ✅ Invalid item_id correctly rejected")
    else:
        print("   ❌ Invalid item_id should have been rejected")
    
    # Step 7: Test invalid item_type
    print("\n7. Testing INVALID interaction (wrong item_type)...")
    interaction_data = {
        "item_id": movie_id,
        "item_type": "invalid",  # Invalid
        "interaction_type": "view"
    }
    
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Response: {json.dumps(result, indent=2)}")
    
    # Pydantic should reject this at validation level
    if response.status_code == 422:
        print("   ✅ Invalid item_type correctly rejected by validation")
    elif response.status_code == 200 and not result.get("success"):
        print("   ✅ Invalid item_type correctly rejected")
    else:
        print("   ❌ Invalid item_type should have been rejected")
    
    # Step 8: Test invalid interaction_type
    print("\n8. Testing INVALID interaction (wrong interaction_type)...")
    interaction_data = {
        "item_id": movie_id,
        "item_type": "movie",
        "interaction_type": "invalid"  # Invalid
    }
    
    response = requests.post(
        f"{BASE_URL}/interactions",
        json=interaction_data,
        headers=headers
    )
    
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Response: {json.dumps(result, indent=2)}")
    
    # Pydantic should reject this at validation level
    if response.status_code == 422:
        print("   ✅ Invalid interaction_type correctly rejected by validation")
    elif response.status_code == 200 and not result.get("success"):
        print("   ✅ Invalid interaction_type correctly rejected")
    else:
        print("   ❌ Invalid interaction_type should have been rejected")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_interactions()
