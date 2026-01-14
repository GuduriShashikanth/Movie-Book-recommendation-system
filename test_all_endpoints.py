#!/usr/bin/env python3
"""
Comprehensive endpoint testing for CineLibre API
Tests all endpoints with various scenarios
"""
import requests
import time
from datetime import datetime

# Configuration
BASE_URL = "https://amateur-meredithe-shashikanth-45dbe15b.koyeb.app"
TEST_EMAIL = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
TEST_PASSWORD = "TestPassword123!"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.END}")

# Global token storage
TOKEN = None

def test_health():
    """Test health check endpoint"""
    print_test("Health Check")
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Status: {res.status_code}")
        data = res.json()
        print(f"Response: {data}")
        
        if res.status_code == 200 and data.get('status') == 'online':
            print_success("API is online and healthy")
            return True
        else:
            print_error("API health check failed")
            return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False

def test_register():
    """Test user registration"""
    print_test("User Registration")
    global TOKEN
    
    try:
        payload = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Test User"
        }
        res = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
        print(f"Status: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            TOKEN = data.get('access_token')
            print_success(f"User registered: {data.get('user', {}).get('email')}")
            print_info(f"Token: {TOKEN[:50]}...")
            return True
        else:
            print_error(f"Registration failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Registration error: {e}")
        return False

def test_login():
    """Test user login"""
    print_test("User Login")
    global TOKEN
    
    try:
        payload = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        res = requests.post(f"{BASE_URL}/auth/login", json=payload, timeout=10)
        print(f"Status: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            TOKEN = data.get('access_token')
            print_success("Login successful")
            return True
        else:
            print_error(f"Login failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Login error: {e}")
        return False

def test_profile():
    """Test get user profile"""
    print_test("Get User Profile")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        res = requests.get(f"{BASE_URL}/auth/me", headers=headers, timeout=10)
        print(f"Status: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            print_success(f"Profile retrieved: {data.get('email')}")
            print(f"User ID: {data.get('id')}")
            print(f"Name: {data.get('name')}")
            return True
        else:
            print_error(f"Profile fetch failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Profile error: {e}")
        return False

def test_search_movies():
    """Test movie search"""
    print_test("Search Movies")
    
    queries = [
        "action thriller",
        "romantic comedy",
        "science fiction",
        "horror movie",
        "family drama"
    ]
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        for query in queries:
            print(f"\n{Colors.YELLOW}Query: '{query}'{Colors.END}")
            res = requests.get(
                f"{BASE_URL}/search",
                params={"query": query, "limit": 5},
                headers=headers,
                timeout=10
            )
            
            if res.status_code == 200:
                data = res.json()
                results = data.get('results', [])
                print_success(f"Found {len(results)} results")
                
                if results:
                    for i, movie in enumerate(results[:3], 1):
                        print(f"  {i}. {movie.get('title')} ({movie.get('language', 'N/A')}) - Similarity: {movie.get('similarity', 0):.3f}")
            else:
                print_error(f"Search failed: {res.status_code}")
            
            time.sleep(0.5)
        
        return True
    except Exception as e:
        print_error(f"Search error: {e}")
        return False

def test_search_books():
    """Test book search"""
    print_test("Search Books")
    
    queries = [
        "python programming",
        "mystery novel",
        "history world war",
        "self improvement",
        "science physics"
    ]
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        for query in queries:
            print(f"\n{Colors.YELLOW}Query: '{query}'{Colors.END}")
            res = requests.get(
                f"{BASE_URL}/search",
                params={"query": query, "item_type": "book", "limit": 5},
                headers=headers,
                timeout=10
            )
            
            if res.status_code == 200:
                data = res.json()
                results = data.get('results', [])
                print_success(f"Found {len(results)} results")
                
                if results:
                    for i, book in enumerate(results[:3], 1):
                        print(f"  {i}. {book.get('title')} - Similarity: {book.get('similarity', 0):.3f}")
            else:
                print_error(f"Search failed: {res.status_code}")
            
            time.sleep(0.5)
        
        return True
    except Exception as e:
        print_error(f"Search error: {e}")
        return False

def test_rate_movie():
    """Test rating a movie"""
    print_test("Rate Movie")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # First, search for a movie
        res = requests.get(
            f"{BASE_URL}/search",
            params={"query": "action", "limit": 1},
            headers=headers,
            timeout=10
        )
        
        if res.status_code != 200:
            print_error("Could not find movie to rate")
            return False
        
        results = res.json().get('results', [])
        if not results:
            print_error("No movies found")
            return False
        
        movie = results[0]
        movie_id = movie.get('id')
        
        print(f"Rating movie: {movie.get('title')}")
        
        # Rate the movie
        payload = {
            "item_id": movie_id,
            "item_type": "movie",
            "rating": 4.5
        }
        res = requests.post(f"{BASE_URL}/ratings", json=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            print_success(f"Movie rated: {data.get('rating')}/5.0")
            return True
        else:
            print_error(f"Rating failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Rating error: {e}")
        return False

def test_get_ratings():
    """Test getting user ratings"""
    print_test("Get My Ratings")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        res = requests.get(f"{BASE_URL}/ratings/me", headers=headers, timeout=10)
        
        if res.status_code == 200:
            ratings = res.json()
            print_success(f"Found {len(ratings)} ratings")
            
            for rating in ratings:
                print(f"  - {rating.get('item_type')}: {rating.get('rating')}/5.0")
            return True
        else:
            print_error(f"Get ratings failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Get ratings error: {e}")
        return False

def test_recommendations():
    """Test personalized recommendations"""
    print_test("Get Recommendations")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        res = requests.get(f"{BASE_URL}/recommendations", headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            items = data.get('popular_items', [])
            method = data.get('method', 'unknown')
            
            print_success(f"Got {len(items)} recommendations using {method}")
            
            for i, item in enumerate(items[:5], 1):
                print(f"  {i}. {item.get('title', 'N/A')}")
            return True
        else:
            print_error(f"Recommendations failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"Recommendations error: {e}")
        return False

def test_list_movies():
    """Test listing movies"""
    print_test("List Movies")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        res = requests.get(
            f"{BASE_URL}/movies",
            params={"limit": 10},
            headers=headers,
            timeout=10
        )
        
        if res.status_code == 200:
            data = res.json()
            movies = data.get('movies', [])
            print_success(f"Listed {len(movies)} movies")
            
            # Check language distribution
            languages = {}
            for movie in movies:
                lang = movie.get('language', 'unknown')
                languages[lang] = languages.get(lang, 0) + 1
            
            print("\nLanguage distribution:")
            for lang, count in languages.items():
                print(f"  {lang}: {count}")
            
            return True
        else:
            print_error(f"List movies failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"List movies error: {e}")
        return False

def test_list_books():
    """Test listing books"""
    print_test("List Books")
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        res = requests.get(
            f"{BASE_URL}/books",
            params={"limit": 10},
            headers=headers,
            timeout=10
        )
        
        if res.status_code == 200:
            data = res.json()
            books = data.get('books', [])
            print_success(f"Listed {len(books)} books")
            
            # Check if new fields exist
            if books:
                sample = books[0]
                print("\nSample book fields:")
                print(f"  Title: {sample.get('title', 'N/A')}")
                print(f"  Authors: {sample.get('authors', 'N/A')}")
                print(f"  Language: {sample.get('language', 'N/A')}")
                print(f"  Categories: {sample.get('categories', 'N/A')}")
            
            return True
        else:
            print_error(f"List books failed: {res.text}")
            return False
    except Exception as e:
        print_error(f"List books error: {e}")
        return False

def run_all_tests():
    """Run all endpoint tests"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}CineLibre API - Comprehensive Endpoint Testing{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"Base URL: {BASE_URL}")
    print(f"Test Email: {TEST_EMAIL}")
    
    results = {}
    
    # Run tests in order
    tests = [
        ("Health Check", test_health),
        ("User Registration", test_register),
        ("User Login", test_login),
        ("Get Profile", test_profile),
        ("Search Movies", test_search_movies),
        ("Search Books", test_search_books),
        ("Rate Movie", test_rate_movie),
        ("Get Ratings", test_get_ratings),
        ("Recommendations", test_recommendations),
        ("List Movies", test_list_movies),
        ("List Books", test_list_books),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print_error(f"Test '{name}' crashed: {e}")
            results[name] = False
        time.sleep(1)
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{status} - {name}")
    
    print(f"\n{Colors.BLUE}Results: {passed}/{total} tests passed ({passed*100//total}%){Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All tests passed!{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  Some tests failed{Colors.END}")

if __name__ == "__main__":
    run_all_tests()
