# Setup Guide for Enhanced Data Sync

## Step 1: Update Database Schema

The enhanced sync engine adds more metadata fields to the books table. You need to run the migration first.

### Option A: Via Supabase Dashboard (Recommended)
1. Go to your Supabase project dashboard
2. Click on "SQL Editor" in the left sidebar
3. Click "New Query"
4. Copy and paste the contents of `add_book_fields.sql`
5. Click "Run" to execute the migration

### Option B: Via Supabase CLI
```bash
supabase db push --file add_book_fields.sql
```

## Step 2: Verify Migration

After running the migration, verify the new columns exist:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'books' 
ORDER BY ordinal_position;
```

You should see these new columns:
- `authors` (TEXT)
- `published_date` (TEXT)
- `categories` (TEXT)
- `language` (TEXT)

## Step 3: Run the Sync

### Option A: Via GitHub Actions (Recommended)
1. Go to your GitHub repository
2. Click on "Actions" tab
3. Select "Daily Content Sync" workflow
4. Click "Run workflow" button
5. Optionally adjust targets:
   - Movie target: 10000 (default)
   - Book target: 5000 (default)
6. Click "Run workflow"

The sync will run in the background and take 30-60 minutes.

### Option B: Run Locally
```bash
# Make sure you have .env file configured
python run_sync.py
```

### Option C: Test with Small Dataset First
```bash
# Test with just 50 movies and 50 books
python test_sync.py
```

## Step 4: Monitor Progress

### GitHub Actions
- Watch the workflow run in the Actions tab
- Check logs for progress updates
- Look for messages like: "✓ Synced 100 movies..."

### Local Run
- Watch console output for progress
- Logs show: language, strategy, page numbers, total count
- Final summary shows synced vs failed counts

## Expected Results

After successful sync:

### Movies
- **Target**: ~10,000 movies
- **Languages**: 12 Indian languages (Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Punjabi, Gujarati, Odia, Assamese, Urdu)
- **Time periods**: 1990-2026
- **Strategies**: Recent, Popular, Top Rated, Box Office

### Books
- **Target**: ~5,000 books
- **Categories**: 34 categories (Fiction, Mystery, Science, Biography, etc.)
- **Languages**: 10 languages (English, Hindi, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Arabic)
- **Ordering**: Newest and Relevance

## Troubleshooting

### "Column does not exist" error
- Run the migration script `add_book_fields.sql` first
- Verify columns exist in Supabase dashboard

### Rate limiting errors
- TMDB: Script automatically waits and retries
- Google Books: Script has built-in delays
- If persistent, reduce targets in workflow inputs

### Memory issues on GitHub Actions
- Reduce targets: Movie=5000, Book=2000
- Or run locally with more resources

### Sync takes too long
- Normal for large datasets (30-60 minutes)
- GitHub Actions has 2-hour timeout
- Can be interrupted and resumed (uses upsert)

## Customization

### Adjust Targets
Edit `.github/workflows/sync.yml` defaults:
```yaml
movie_target:
  default: '10000'  # Change this
book_target:
  default: '5000'   # Change this
```

### Change Schedule
Edit the cron expression:
```yaml
schedule:
  - cron: '0 0 * * *'  # Daily at midnight UTC
  # Examples:
  # '0 */6 * * *'  # Every 6 hours
  # '0 0 * * 0'    # Weekly on Sunday
  # '0 0 1 * *'    # Monthly on 1st
```

### Add More Languages (Movies)
Edit `api/sync_engine.py`:
```python
languages = ['hi', 'te', 'ta', 'kn', 'ml', 'bn', 'mr', 'pa', 'gu', 'or', 'as', 'ur', 'ne', 'si']
```

### Add More Categories (Books)
Edit `api/sync_engine.py`:
```python
categories = [
    "fiction", "mystery", "history", "science", "biography",
    # Add your categories here
    "manga", "comics", "graphic novels"
]
```

## Next Steps

After successful sync:
1. Check Supabase dashboard for row counts
2. Test search API with new content
3. Verify recommendations work with more data
4. Monitor API performance
5. Schedule regular syncs (already configured)
