# Quick Fix Steps - Get More Data

## What's Been Fixed

✅ Enhanced sync_engine.py to fetch:
- **10,000 movies** (up from 3,000) - 6 languages: English, Telugu, Hindi, Tamil, Kannada, Malayalam
- **5,000 English books** (up from 500) - 34 categories, multiple orderings

✅ Updated GitHub Actions workflow with:
- Configurable targets via workflow inputs
- 2-hour timeout for large syncs
- Environment variable support

✅ Added database migration for new book fields:
- authors, published_date, categories, language

## What You Need to Do

### Step 1: Run Database Migration (REQUIRED)
Go to Supabase SQL Editor and run `add_book_fields.sql`:

```sql
-- Copy and paste this in Supabase SQL Editor
ALTER TABLE books 
ADD COLUMN IF NOT EXISTS authors TEXT,
ADD COLUMN IF NOT EXISTS published_date TEXT,
ADD COLUMN IF NOT EXISTS categories TEXT,
ADD COLUMN IF NOT EXISTS language TEXT;

CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
CREATE INDEX IF NOT EXISTS idx_books_categories ON books(categories);
CREATE INDEX IF NOT EXISTS idx_books_published ON books(published_date);
```

### Step 2: Commit and Push Changes
```bash
git add .
git commit -m "Enhanced sync engine for 10k movies (6 languages) and 5k English books"
git push
```

### Step 3: Trigger Sync via GitHub Actions
1. Go to GitHub → Actions tab
2. Select "Daily Content Sync"
3. Click "Run workflow"
4. Leave defaults (10000 movies, 5000 books) or adjust
5. Click "Run workflow" button

### Step 4: Wait and Monitor
- Sync takes 30-60 minutes
- Watch logs in Actions tab
- Look for "🎉 SYNC COMPLETE" message

## Alternative: Test Locally First

```bash
# Test with small dataset (50 each)
python test_sync.py

# Or run full sync locally
python run_sync.py
```

## Files Changed

- ✅ `api/sync_engine.py` - Enhanced data fetching
- ✅ `.github/workflows/sync.yml` - Added workflow inputs
- ✅ `add_book_fields.sql` - Database migration
- ✅ `SYNC_SETUP.md` - Detailed guide
- ✅ `run_sync.py` - Local sync script
- ✅ `test_sync.py` - Test script

## That's It!

After the sync completes, you'll have:
- ~10,000 movies in 6 languages (English, Telugu, Hindi, Tamil, Kannada, Malayalam)
- ~5,000 English books across 34 categories
- Better search results
- More diverse recommendations
