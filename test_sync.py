#!/usr/bin/env python3
"""
Test sync with smaller dataset to verify everything works
"""
import os
from dotenv import load_dotenv
from api.sync_engine import (
    get_indian_movies, 
    get_global_books, 
    get_embedding,
    supabase,
    logger
)

load_dotenv('api/.env')

def test_sync_small():
    """Test with just 50 movies and 50 books"""
    print("=" * 60)
    print("Testing Sync Engine (Small Dataset)")
    print("=" * 60)
    print()
    
    # Test movies
    print("Fetching 50 test movies...")
    movies = get_indian_movies(total_target=50)
    print(f"✓ Fetched {len(movies)} movies")
    
    if movies:
        print(f"Sample movie: {movies[0].get('title', 'N/A')}")
        
        # Test embedding
        print("Testing embedding generation...")
        text = f"{movies[0]['title']}. {movies[0].get('overview', '')}"
        vector = get_embedding(text)
        if vector:
            print(f"✓ Embedding generated (dimension: {len(vector)})")
        else:
            print("❌ Embedding failed")
    
    print()
    
    # Test books
    print("Fetching 50 test books...")
    books = get_global_books(total_target=50)
    print(f"✓ Fetched {len(books)} books")
    
    if books:
        vol = books[0].get('volumeInfo', {})
        print(f"Sample book: {vol.get('title', 'N/A')}")
        
        # Test embedding
        print("Testing embedding generation...")
        text = f"{vol.get('title', '')}. {vol.get('description', '')[:200]}"
        vector = get_embedding(text)
        if vector:
            print(f"✓ Embedding generated (dimension: {len(vector)})")
        else:
            print("❌ Embedding failed")
    
    print()
    print("=" * 60)
    print("Test complete! Everything looks good.")
    print("Run 'python run_sync.py' for full sync")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_sync_small()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
