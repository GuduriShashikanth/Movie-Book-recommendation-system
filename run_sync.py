#!/usr/bin/env python3
"""
Quick script to run the data sync engine
This will populate your database with movies and books
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('api/.env')

# Import and run sync
from api.sync_engine import run_sync

if __name__ == "__main__":
    print("=" * 60)
    print("CineLibre Data Sync Engine")
    print("=" * 60)
    print()
    
    # Check environment variables
    required_vars = ['TMDB_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("Please check your api/.env file")
        sys.exit(1)
    
    print("✓ Environment variables loaded")
    print()
    
    # Confirm before running
    print("This will fetch and sync:")
    print("  • ~10,000 Indian movies (multiple languages)")
    print("  • ~5,000 global books (multiple categories)")
    print()
    print("⚠️  This may take 30-60 minutes depending on your connection")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Sync cancelled")
        sys.exit(0)
    
    print()
    print("Starting sync...")
    print("=" * 60)
    print()
    
    try:
        run_sync()
        print()
        print("=" * 60)
        print("✅ Sync completed successfully!")
        print("=" * 60)
    except KeyboardInterrupt:
        print()
        print("⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Sync failed: {e}")
        sys.exit(1)
